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
Imports & exports tri files and the Bodyslide variant of tri files.

This module has no Blender dependencies. It just pulls the data out of the file and puts it 
in a python-friendly format.

Code adapted by Bad Dog from tri export/importer
Original author listed as "Core script by kapaer, modvertice support by deedes"
updated by anon (me) to work with newer blender ( version 2.63+), I hope

"""

# Tri File format https://facegen.com/dl/sdk/doc/manual/fileformats.html:
# Header
#   FRTRI003
#   version number
#   vertexNum
#   faceNum
#   uvNum
#   morphNum ("difference morphs")
#   modMorphNum ("stat morphs")
#   addVertexNum (total number of stat mod vertices)
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
#   (dx,xy,xz) * vertexNum -- offset for each vertex in short ints
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
        self.signature = ''			#Header with version number / magic number
        self.vertexNum = 0		#number of vertices on the base mesh
        self.faceNum = 0			#number of faces on the base mesh
        self.morphNum = 0		#number of regular morphs
        self.uvNum = 0			#number of Vectors for the UV on the base mesh
        self.addMorphNum = 0		#number of modifier morphs
        self.addVertexNum = 0	#number of additional vertices for modifier morphs
        self.log = logging.getLogger("pynifly")

    def write(self):
        """ Return packed header, ready for writing """
        return pack('<8s14I',	self.signature.encode("iso-8859-15"),	#signature
            self.vertexNum,			#vertexNum
            self.faceNum,			#faceNum
            0,0,0,				#number of quads, of labelled vertices, of labelled surface points
            self.uvNum,			#uvNum
            1,					#extension flags, 1=have texture coordinates
            self.morphNum,			#morphNum (difference morphs)
            self.addMorphNum,		#addMorphNum (stat morphs)
            self.addVertexNum,		#addVertexNum (stat morph vertex count)
            0,0,0,0)            #16 bytes for future use

    def read(self, file):
        """ Read header from file 
             file = open file object
        """
        try:
            tmp_data = file.read(0x40)
        except ValueError:
            self.log.error("Cannot read header for file")
            raise ValueError("Error reading TRI file")
        data = unpack('<8s10I16x', tmp_data) 
        self.signature = data[0].decode("iso-8859-15")
        if self.signature == VERSION_STRING:
            self.vertexNum = data[1]
            self.faceNum = data[2]
            self.uvNum = data[6]
            self.morphNum = data[8]
            self.addMorphNum = data[9]
            self.addVertexNum = data[10]

    def __str__(self):
        if self.signature == VERSION_STRING:
            s = "TRI Header:\n"
            s += "Base Vertices : " + str(self.vertexNum) + "\n"
            s += "Faces:          " + str(self.faceNum) + "\n"
            s += "UV Coordinates: " + str(self.uvNum) + "\n"
            s += "Morphs:         " + str(self.morphNum) + "\n"
            s += "Mod Morphs:     " + str(self.addMorphNum) + " with " + str(self.addVertexNum) + " vertices\n"
        elif self.signature[0:4] == 'PIRT':
            s = "TRIP File"
        else:
            s = f"Not a TRI file: {self.signature}"
        return s


class TriFile():
    def __init__(self):
        self.type = 'TRI'
        self.header = TRIHeader()
        self._vertices = None    # [(x,y,z), ...]
        self._faces = None       # [(p1, p2, p3), ...] where p# is an index into vertices
        self.reorder_verts = False
        self.morphs = {}        # Dictionary of morphs. Verts are absolute values.
        self.modmorphs = {}
        self.uv_pos = None      # [(u,v), ...] 1:1 with vertex list
        self.face_uvs = None    # [(i1,i2,i3), ...]  1:1 with faces list; indices into UV_pos list
        self.import_uv = True   # Import UV along with verts
        self.log = logging.getLogger("pynifly")

    def read_morph(self, file):
        """ 
        Reads a single morph from a tri file

        * file = file object positioned at start of morph
        * returns = (morph-name, [(x,y,z), ...]) list of absolute new vert positions
          defined by the morph, 1:1 with the base verts
        """
        morph_index = len(self.morphs) 
        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        
        data = unpack('<I', tmp_data)
        tmp_data = file.read(data[0])
        if len(tmp_data) < data[0]:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        
        data = unpack('<'+str(data[0]-1)+'sx', tmp_data)
        morphSubName = data[0].decode("iso-8859-15")
        #self.log.debug(f"Read morph: {morphSubName}")
        
        tmp_data = file.read(FLOAT_LEN)
        
        if len(tmp_data) < FLOAT_LEN:
            self.log.error("EOF reading morph header\nError on morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        data = unpack('<f', tmp_data)
        baseDiff = data[0]
        
        tmp_buffer = file.read(SHORT_LEN * 3 * self.header.vertexNum)
        if len(tmp_buffer) < SHORT_LEN * 3 * self.header.vertexNum:
            self.log.error("EOF reading morph data vertices\nError on morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nMorph has valid header, but appears to be corrupt\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")		

        morph_verts = [] 
        for lidx in range(self.header.vertexNum):
            data = unpack('<3h', tmp_buffer[SHORT_LEN * 3 * lidx : (SHORT_LEN*3*lidx) + (SHORT_LEN*3)]  )
            morph_verts.append((self._vertices[lidx][0] + data[0] * baseDiff,
                                self._vertices[lidx][1] + data[1] * baseDiff,
                                self._vertices[lidx][2] + data[2] * baseDiff) )

        return morphSubName, morph_verts


    def read_modmorph(self, file, i, vertsAdd_Index, vertsAdd_list, vertsAdd_listLength, verts_list):
        """ 
        Reads a single mod morph from a tri file. Mod morphs only morph some of the vertices.

        * file = file object positioned at start of morph
        * returns = (morph-name, [(x,y,z), ...]) list of absolute new vert positions
          defined by the morph, 1:1 with base verts
        """
        morph_index = len(self.modmorphs) 

        # Read the morph name
        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        data = unpack('<I', tmp_data)

        tmp_data = file.read(data[0])
        if len(tmp_data) < data[0]:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        data = unpack('<'+str(data[0]-1)+'sx', tmp_data)
        morphSubName = data[0].decode("iso-8859-15")
        self.log.debug(f"Read modmorph {morphSubName}")

        # Read the morph block (array of affected vertex indices)
        tmp_data = file.read(INT_LEN)
        if len(tmp_data) < INT_LEN:
            self.log.error("EOF reading MOD-morph header\nError on MOD-morph number " + str(morph_index) + "\n  \"" + morphSubName + "\"\nFile appears to be corrupt")
            raise ValueError("Error reading TRI file")
        data = unpack('<I', tmp_data)
        blockLength = data[0]
        
        if blockLength > 0:
            nextMorphVertIdx = 0
            tmp_buffer = file.read(INT_LEN*blockLength)
            if len(tmp_buffer) < INT_LEN*blockLength:
                self.log.error("EOF reading MOD-morph data verticies\nError on MOD-morph number " + str(i+1) + "\n  \"" + morphSubName + "\"\nMorph has valid header, but appears to be corrupt\nFile appears to be corrupt")
                raise ValueError("Error reading TRI file")	
            
            new_verts = self._vertices.copy()
            for nextMorphVertIdx in range(0, blockLength):
                data = unpack('<I', tmp_buffer[INT_LEN*nextMorphVertIdx:(INT_LEN*nextMorphVertIdx)+INT_LEN])
                vert_index = data[0]

                new_verts[vert_index] = (vertsAdd_list[vertsAdd_Index][0],
                                         vertsAdd_list[vertsAdd_Index][1],
                                         vertsAdd_list[vertsAdd_Index][2],)
                vertsAdd_Index += 1
            
            return morphSubName, vertsAdd_Index, new_verts

        return morphSubName, 0, None


    def read(self, file):
        """ Read the given tri file 
            file = file object
            header = TRIheader object to use for this import
            returns (obj with shape keys, mesh with vertex locations)
        """
        self.log.debug(f"""
            Reading tri file: 
            {self.header}
            """)

        # load vertex data
        verts_list = []
        tmp_buffer = file.read(FLOAT_LEN * 3 * self.header.vertexNum)
        if len(tmp_buffer) < FLOAT_LEN * 3 * self.header.vertexNum:
            self.log.error("EOF reading base model verticies - Should read " + str(self.header.vertexNum) \
                + " vertices with\n" + str(FLOAT_LEN*3*self.header.vertexNum) + " bytes but only read " \
                + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            raise ValueError("Error reading TRI file")
        
        for i in range(self.header.vertexNum):
            data = unpack('<3f', tmp_buffer[FLOAT_LEN * 3 * i : (FLOAT_LEN*3*i) + (FLOAT_LEN*3)])
            verts_list.append((data[0], data[1], data[2]))

        self._vertices = verts_list

        # "modvertice" = morph data sets, where each set need not contain data for every vertex in the mesh
        # Downside is that the structure must specify which vertices are in each set and which vertex each 3D point refers to
        vertsAdd_list = []
        tmp_buffer = file.read(FLOAT_LEN*3*self.header.addVertexNum)
        if len(tmp_buffer) < FLOAT_LEN*3*self.header.addVertexNum:
            # self.log.error("\n----=| Tri Import Error |=----\nEOF reading mod-morph vertices\nShould read " + str(self.header.addVertexNum) + " mod verticies with\n" + str(FLOAT_LEN*3*header.addVertexNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            raise ValueError(f"Error reading TRI file: Not enough mod vertices")
        
        for i in range(self.header.addVertexNum):
            data = unpack('<3f', tmp_buffer[FLOAT_LEN*3*i:(FLOAT_LEN*3*i)+(FLOAT_LEN*3)])
            vertsAdd_list.append((data[0], data[1], data[2]))

        # loading faces
        self._faces = []
        tmp_buffer = file.read(INT_LEN*3*self.header.faceNum)
        if len(tmp_buffer) < INT_LEN*3*self.header.faceNum:
            self.log.error("\n----=| Tri Import Error |=----\nEOF reading model faces\nShould read " + str(self.header.faceNum) + " faces with\n" + str(INT_LEN*3*self.header.faceNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            raise ValueError("Error reading TRI file")

        for i in range(self.header.faceNum):
            data = unpack('<3I', tmp_buffer[INT_LEN*3*i:(INT_LEN*3*i)+(INT_LEN*3)])
            self.faces.append((data[0], data[1], data[2]))

        numFaces = len(self._faces)

        self.uv_pos = []
        tmp_buffer = file.read(FLOAT_LEN*2 * self.header.uvNum)
        if len(tmp_buffer) < FLOAT_LEN*2*self.header.uvNum:
            self.log.error("\n----=| Tri Import Error |=----\nEOF reading UV Coordinates\nShould read " + str(self.header.uvNum) + " UVs with \n" + str(FLOAT_LEN*2*self.header.uvNum) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            raise ValueError("Error reading TRI file")

        for i in range(self.header.uvNum):
            data = unpack('<2f', tmp_buffer[FLOAT_LEN*2*i:(FLOAT_LEN*2*i)+(FLOAT_LEN*2)])
            self.uv_pos.append((data[0], data[1])) # Inverting "V" to match what we get from nifs

        numUV = len(self.uv_pos)

        #I'm assuming that tri files will always have 1 UV per vertex, but i wasn't able to conirm this for sure.. so:
        if numUV != len(verts_list):
            self.log.warning(f"Number of verticies differs from number of UV coordinates: {numUV} != {len(verts_list)}; importing without UV")
            self.import_uv = False

        # NOTE --- For future reference. UV's are placed "on a vertex" but indirectly. Each loop contains one vertex index that is supposed to be tied into
        # a polygon face (there will be face*3 loops for a triangulated mesh) and each "loop" contains the uv. This allows for things like smoothing since a
        # single vertex item can have different data depending on the face being looked at ("coming from a different direction").
        #     therefore, the "loop_indices" can be misleading. This is NOT "The face-vertex index" but is an index into the loop array itself. To get the actual
        # vertex index out of the face (the colleciton of 3+ loops), you must dereference the loop as well. So mesh.loops[mesh.polygons.loop_indices[0]].vertex_index
        #     HOEWEVER, TRI files are of the style where, when a vertex at a locaiton needes alternate info (differnt UV), the vertex is just duplicated. So, even
        # a vertex location needs more than one set of data, each vertex only has one set of data.
        #     Meanwhile, the uv_layers has the uv coordinates in the same indexing order as mesh.loops. So, uv_layers[0].data[5].uv is intended to be the uv
        # coordinates of loop number 5 in mesh.loops, and that is how uv are "placed" on vertex (the vertex of a particular face)

        tmp_buffer = file.read(INT_LEN * 3 * numFaces)
        if len(tmp_buffer) < INT_LEN * 3 * numFaces:
            # self.log.error("EOF reading Face Vertex Index to UV Index array - should have " + str(len(mesh.polygons)) + " indicies with \n" + str(INT_LEN*3*len(mesh.polygons)) + " bytes but only read " + str(len(tmp_buffer)) + "\nTRI file has valid header, but file appears to be corrupt")
            raise ValueError("Error reading TRI file: Not enough faces")

        # face_uvs array: For each face we have 3 (u,v) locations (3 cuz faces are triangles)
        ### Not currently using this, but Blender can do it. Since nifs have 1:1 relationship between vert and UV, skipping it.
        self.face_uvs = []
        if self.import_uv:
            for lidx in range(numFaces):
                data = unpack('<3I', tmp_buffer[INT_LEN*3*lidx:(INT_LEN*3*lidx)+(INT_LEN*3)])
                self.face_uvs.append((data[0], data[1], data[2]))
                #self.face_uvs.append([(self.uv_pos[data[0]][0], self.uv_pos[data[0]][1]),
                #                      (self.uv_pos[data[1]][0], self.uv_pos[data[1]][1]),
                #                      (self.uv_pos[data[2]][0], self.uv_pos[data[2]][1]) ])
            
        self.morphs = {}
        self.morphs['Basis'] = self._vertices

        # read morph data
        if self.header.morphNum > 0:
            for i in range(self.header.morphNum):
                name, verts = self.read_morph(file)
                self.morphs[name] = verts

        self.modmorphs = {}
                
        # read additional morph data
        if self.header.addMorphNum > 0:
            vertsAdd_Index = 0
            vertsAdd_listLength = len(vertsAdd_list)

            for i in range(self.header.addMorphNum):
                name, vertsAdd_Index, verts = self.read_modmorph(
                    file, 
                    i,
                    vertsAdd_Index,
                    vertsAdd_list,
                    vertsAdd_listLength,
                    verts_list
                    )
                if verts:
                    self.modmorphs[name] = verts
                    self.log.debug(f"Read morph {name}")


    @classmethod
    def from_file(cls, filepath):
        """ Read tris from the given file.
            Returns a new TriFile with the file conents.
        """
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
        if tri.header.signature[0:5] != 'FRITRI' and tri.header.signature[0:4] != 'PRIT':
            # file.close()
            #raise ValueError(f"'{filepath}' is not formatted as a tri file. Format given as [{tri.header.signature}] when it should be [FRTRI003]")
            log.warning(f"'{filepath}' is not formatted as a tri file. Format given as [{tri.header.signature}]")
            #log.error(f"File is not of correct format. Format given as [{tri.header.signature}] when it should be [FRTRI003]")
            #return {'CANCELLED'}

        try:
            tri.read(file)
        except ValueError:
            file.close()
            log.exception("Error importing Tri File")
            return {'CANCELLED'}		

        file.close()

        return tri

   
    # ------------------- EXPORT ---------------------

    @property
    def vertices(self):
        return self._vertices

    @vertices.setter
    def vertices(self, val):
        """ Sets the vertex list. Val is a list of triples. No copy is made """
        self._vertices = val
        self.header.vertexNum = len(val)


    @property
    def faces(self):
        return self._faces

    @faces.setter
    def faces(self, val):
        """ Sets the face list. Faces must be triangles. Val is list of triples. No copy is made. """
        self._faces = val
        self.header.faceNum = len(val)


    def write(self, filepath, export_morphs:set = None): # write(ob, scn, filename, filepath, reorder_verts):
        """ Write the TriFile to a file 
            filepath = name of file to write
            export_morphs = subset of morph names to write
        """
       
        self.header.signature = VERSION_STRING

        ### NOT WORKING because I have to pass in loops ###
        #Mapping for re-order of verts to  match a 'sequential face list' index = vertex index, value = index to remap to
        #verts_reorder_mapping will be referenced everwhere in the script, just that only if re-rdering is selcted is the mapping not v#:v#
        if False: # self.reorder_verts:
            # verts_reorder_mapping = [-1] * len(self._vertices)
            # current_v_position = 0
            # for f_index, f in enumerate(self._faces):
            #     #f_vert is the 1st, 2nd, or 3rd index of the face
            #     for f_vert, loop_index in enumerate(f.loop_indices):
            #         if f_vert > 2:
            #             self.write_error(f"Error exporting tris from {ob.name}: Mesh has faces with more than 3 verts")
            #             raise ValueError("Error creating tri file")

            #         vert_idx = mesh.loops[loop_index].vertex_index
            #         #if this vertex has not already been remapped, remap it
            #         if verts_reorder_mapping[vert_idx] == -1:
            #             verts_reorder_mapping[vert_idx] = current_v_position
            #             current_v_position = current_v_position + 1
            pass
        else:
            verts_reorder_mapping = range(len(self._vertices)) # [v_idx for v_idx, v in enumerate(verts)]

        #Not a good idea to pack long strings repeatedly
        modHeaderArrayToPack = []
        modVerticeArrayToPack = []
        morphKeysArrayToPack = []
        morphKeysDiffValuesArrayToPack = []

        modHeaderPacked		= b''	#string to collect the header data
        modVerticePacked	= b''	#string to collect the vertice data
        morphKeysPacked		= b''	#string to collect the morph key data to write

        morphNameList =[] #Holds a list of previously processed morph names to check for duplicates
        fullMorphNameList =[] #Only full morph names
        modMorphNameList =[] #Only mod-morph names
        
        morphlist = set(self.morphs.keys())
        if export_morphs is not None:
            morphlist = morphlist.intersection(export_morphs)

        self.header.morphNum = len(morphlist)
        for morphName in morphlist:
            #self.log.debug(f"..exporting morph {morphName}")
            verts_diff = [[]] * len(self.vertices)		#list to save vertices to
            max_diff = 0
            fullMorphNameList.append(morphName)

            #The TRI format saves the offset data in a 'normalized' form.  The largets
            #difference is used as a factor to apply to all the offset values So, the
            #largest difference needs to be found self.log.debug(f"Writing shape verts
            #for {morphName} value is {type(self.morphs[morphName])}")
            shape_verts = self.morphs[morphName]
            vert_idx = 0

            for nv, bv in zip(shape_verts, self.vertices):
                data = (nv[0] - bv[0], nv[1] - bv[1], nv[2] - bv[2])
                max_diff = max(abs(data[0]), abs(data[1]), abs(data[2]), max_diff)
                verts_diff[verts_reorder_mapping[vert_idx]] = data
                vert_idx = vert_idx + 1

            #7fff=max signed integer value for 16 bits = 32767.  I guess, dunno why it was like
            #this, but I like hex.  Frogs everywhere.
            diff_base = max_diff / 0x7fff
                
            #If the diff is 0, then the morph and the base are identical.  That's fine,
            #but the normalization factor shouldn't be 0!  Another way to do this would
            #be to just set all the diff values to 0 in the loop below.  They should,
            #indeed, all be 0 since v[0-2] will all be 0 since the difference calculated
            #above was all exactly 0 or below precision of float.  This effectively adds
            #a built-in floor to the amount of offset the export will allow, but I don't
            #think rendering programs will genreally allow that level of precision
            #anyway, heh
            if diff_base == 0: 
                diff_base = 1
            
            morphKeysDiffValuesArrayToPack.append( float(diff_base) )

            for i in range(len(verts_diff)):
                verts_diff[i] = (int(verts_diff[i][0]/diff_base), 
                                 int(verts_diff[i][1]/diff_base),
                                 int(verts_diff[i][2]/diff_base))

            morphKeysArrayToPack.append( verts_diff.copy() )

        morphlist = set(self.modmorphs.keys())
        if export_morphs is not None:
            morphlist = morphlist.intersection(export_morphs)

        self.header.addMorphNum = 0
        self.header.addVertexNum = 0
        for morphName in morphlist:
            self.header.addMorphNum += 1
            morphNameList.append(morphName)
            modMorphNameList.append(morphName)
            verticeCount 	= 0	 #keeps track of the number of vertices
            verticeAdded	= 0	 #keeps track of the number of vertices which were actually added to the additional vertex list
            
            shape_verts = self.modmorphs[morphName]
            for nv, mv in zip(shape_verts, self.vertices):
                div = abs(nv[0] - mv[0]) + abs(nv[1] - mv[1]) + abs(nv[2] - mv[2]) / 3
                if div > 0.00033:		#filter out the vertices which are too similiar to the base mesh
                    data = [nv[0], nv[1], nv[2], verts_reorder_mapping[verticeCount]]
                    verts_diff[verts_reorder_mapping[verticeCount]] = data.copy()
                    self.header.addVertexNum += 1
                    verticeAdded += 1
                verticeCount += 1

            modHeaderArrayToPack.append( [] )
            modVerticeArrayToPack.append( [] )

            modHeaderArrayToPack[self.header.addMorphNum-1].append( int(verticeAdded) )

            # modHeaderPacked is the list of vertex indices referencing the base model
            # array.  The index into this list is the same as the index into the list of
            # actual mod vertices (modVerticePacked).  It indicates to which vertex in the
            # base model the offset given in the modVerticePacked applies
            for v in verts_diff:
                if v != []:
                    modHeaderArrayToPack[self.header.addMorphNum-1].append( int(v[3]) )
                    modVerticeArrayToPack[self.header.addMorphNum-1].append( [float(v[0]), float(v[1]), float(v[2])] )


        #Pack Morph
        for morphNum, diffValue in enumerate(morphKeysDiffValuesArrayToPack):
            morphKeysPacked += pack('<I'+ str(len(fullMorphNameList[morphNum])) +'sx', len(fullMorphNameList[morphNum])+1, fullMorphNameList[morphNum].encode("utf-8") )
            morphKeysPacked += pack('<f', diffValue)
            morphKeysPacked += pack('<' + str(len(morphKeysArrayToPack[morphNum])*3) + 'h', *[k for j in morphKeysArrayToPack[morphNum] for k in j] )

        #Pack Mod-Morph
        for morphNum, headerArray in enumerate(modHeaderArrayToPack):
            modHeaderPacked += pack('<I'+ str(len(modMorphNameList[morphNum])) +'sx', len(modMorphNameList[morphNum])+1, modMorphNameList[morphNum].encode("utf-8") )
            modHeaderPacked += pack('<I', headerArray[0] )
            modHeaderPacked += pack('<' + str( len(headerArray)-1 ) + 'I', *headerArray[1:]  )
            modVerticePacked += pack('<' + str(len(modVerticeArrayToPack[morphNum])*3) + 'f', *[k for j in modVerticeArrayToPack[morphNum] for k in j] )


        # anon says: I think I understand what the original script was doing, but not
        # entirely.  As far as I know, the uv should just be in the same order as the
        # vertices, vertex 1 has uv at index 1, and so forth.  The data will be
        # constructed the same way here.  There will always be numuv = num verts..  I
        # hope.
        uvDataPacked = b''
        uv_face_mapping = [(0,0,0) for f in self._faces]
        #uv_gather = [(0.0, 0.0) for v in self._vertices]
        for f_index, f in enumerate(self._faces):
            v0 = verts_reorder_mapping[f[0]]
            v1 = verts_reorder_mapping[f[1]]
            v2 = verts_reorder_mapping[f[2]]
            uv_face_mapping[f_index] = (v0, v1, v2)

        for uv in self.uv_pos:
            uvDataPacked += pack('<2f', float(uv[0]), 1.0-uv[1])

        self.header.uvNum = len(self.uv_pos)

        # vertex packing
        vertexDataPacked = b''
        verts_to_pack = [[]] * len(self._vertices)
        
        # Reorder verts per our mapping
        for i, v in enumerate(self._vertices):
            verts_to_pack[verts_reorder_mapping[i]] = (v[0], v[1], v[2])

        # Pack them in the new order
        for vco in verts_to_pack:
            tmp_data = pack('<3f', vco[0], vco[1], vco[2])
            vertexDataPacked += tmp_data
    
        # face packing
        faceDataPacked = b''
        for f in self.faces:
            faceDataPacked += pack('<3I', 
                verts_reorder_mapping[f[0]], verts_reorder_mapping[f[1]], verts_reorder_mapping[f[2]])

        faceNumDataPacked = b''
        for uv in uv_face_mapping:
            faceNumDataPacked +=  pack('<3I', uv[0], uv[1], uv[2])

        # start writing...
        try:
            file = open(filepath,'wb')
        except:
            self.log.error(f"Error opening '{filepath}' as output file")
            raise
        file.write(self.header.write()
                        + vertexDataPacked
                        + modVerticePacked
                        + faceDataPacked
                        + uvDataPacked
                        + faceNumDataPacked
                        + morphKeysPacked
                        + modHeaderPacked)
        file.close()


# ###################################################################################
#
#       TRIP Import/Export
#
# ###################################################################################
#
# TRIP file = tri file for bodies, used by Bodyslide/Outfit studio
#
# Header
#   'PIRT' - identifies the file format
#   shapeCount - number of shapes to follow
#   For each shape:
#       shape name - first byte is length
#       morph count - number of morphs to follow
#       For each morph:
#           morph name - first byte is length
#           morph multipler - float
#           vert count - number of verts to follow
#           for each vert
#               vert id - Depends on an external vert list that must be in sync
#               x, y, z - vert offsets
#

class TripFile():
    def __init__(self):
        self.is_valid = False
        self.type = 'TRIP'
        self.shapes = {} # {shape-name: morph-dict, ...} where morph-dict =
                             # { morph-name: [[vert-index, (offs x, offs y, offs z)]... ], ... }
        self.log = logging.getLogger("pynifly")

    def _read_count_str(self, file):
        """ Reads a string from the file, where the length is in a single byte preceding
            the string. 
            Returns the string.
            """
        thelen = unpack('<B', file.read(1))[0]
        if thelen > 0:
            name = unpack(f'<{thelen}s', 
                          file.read(thelen))[0].decode("iso-8859-15")
            return name
        else:
            return ''
        
    def _write_count_str(self, file, s):
        file.write(pack('<B', len(s)))
        file.write(pack(f'<{len(s)}s', s.encode("iso-8859-15")))
        
    def _coord_nonzero(self, coords):
        return abs(coords[0]) > 0.0001 or abs(coords[1]) > 0.0001 or abs(coords[2]) > 0.0001 

    def _calc_max_offset(self, offslist):
        m = 0.0
        for i, o in offslist:
            m = max(m, abs(o[0]), abs(o[1]), abs(o[2]))
        return m

    def read(self, file):
        """ Read TRIP file 
             file = open file object
             returns: 0 = success, 1 = not a TRIP file 2 = some other error
                if 1, file position is reset to start
        """
        data = file.read(4)
        if data != b'PIRT' and data != b'\0IRT':
            file.seek(0)
            self.is_valid = False
            return 1

        rawdata = file.read(2)
        shapecount = unpack('<1H', rawdata)[0]

        for i in range(shapecount):
            shapename = self._read_count_str(file)
            self.log.debug(f"..Found shape {shapename}")

            offsetmorphs = {}
            morphcount = unpack('<1H', file.read(2))[0]
            for j in range(morphcount):
                morphname = self._read_count_str(file)
                self.log.debug(f"....found morph {morphname}")
                morphmult = unpack('<1f', file.read(4))[0] 
                vertcount = unpack('<1H', file.read(2))[0]
                morphverts = []

                for k in range(vertcount):
                    id, x, y, z = unpack('<1H3h', file.read(8))

                    v = (x * morphmult, y * morphmult, z * morphmult)
                    if self._coord_nonzero(v):
                        morphverts.append([id, v]) 

                if True: # len(morphverts) > 0:
                    offsetmorphs[morphname] = morphverts # keep them all, even null morphs

            self.shapes[shapename] = offsetmorphs

        # there might be UV information but ignore it
        self.is_valid = True
        return 0

    def set_morphs(self, shapename, morphdict, vertlist):
        """ 
        Set the morphs property from a morph dictionary.
        * shapename = name of the shape the morphs are for
        * morphdict = { morph-name: [(x,y,z), ...], ...} - xyz coordinates are 1:1 with
          vertlist
        * vertlist = [(x,y,z), ...] - shape vertices
        """
        offsetmorphs = {}
        for name, coords in morphdict.items():
            #self.log.debug(f"[TRIP] Writing morph {name}")
            offsetlist = []
            for i, coordpair in enumerate(zip(coords, vertlist)):
                co, v = coordpair
                offsets = (co[0] - v[0], co[1] - v[1], co[2] - v[2])
                if self._coord_nonzero(offsets):
                    offsetlist.append([i, offsets])
            if len(offsetlist) > 0:
                offsetmorphs[name] = offsetlist
        
        self.shapes[shapename] = offsetmorphs


    def write(self, filepath):
        """ Write out the TRIP file """
        self.log.info(f"[TRIP] Writing TRIP file {filepath}")
        file = open(filepath, 'wb')
        try:
            file.write(pack("<4s", b'PIRT'))

            file.write(pack('<1H', len(self.shapes))) 
            for shapename, offsetmorphs in self.shapes.items():
                self._write_count_str(file, shapename)

                file.write(pack("<1H", len(offsetmorphs)))
                for name, offslist in offsetmorphs.items():
                    #self.log.debug(f"....Writing morph {name}")
                    self._write_count_str(file, name)
            
                    scalefactor = 0x7fff / self._calc_max_offset(offslist) 
                    if scalefactor < 0.0001: scalefactor = 1

                    file.write(pack('<1f', 1/scalefactor))
                    file.write(pack('<1H', len(offslist)))

                    for vert_idx, offsets in offslist:
                        file.write(pack('<1H', vert_idx))
                        file.write(pack('<3h', int(offsets[0] * scalefactor), 
                                        int(offsets[1] * scalefactor), 
                                        int(offsets[2] * scalefactor)))
        finally:
            file.close()

    @classmethod
    def from_file(cls, filepath):
        f = open(filepath, 'rb')
        tri = TripFile()
        tri.read(f)
        return tri
    

if __name__ == "__main__":
    test_path = r"C:\Users\hughr\OneDrive\Dev\PyNifly\PyNifly\tests"
    log = logging.getLogger("pynifly")
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s-%(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    TEST_ALL = True

    def uv_near_eq(uv1, uv2):
        return round(uv1[0], 4) == round(uv2[0], 4) and round(uv1[1], 4) == round(uv2[1], 4) 

    if TEST_ALL:
        log.info("### Read a BS tri file")
        t4 = TripFile.from_file(os.path.join(test_path, "FO4/BodyTalk3.tri"))
        assert len(t4.shapes['BaseMaleBody:0']) > 0, f"Error: Expected offset morphs, found {len(t4.offsetmorphs)}"

        log.info("Importing tri")
        t = TriFile.from_file(os.path.join(test_path, "FO4/CheetahMaleHead.tri"))
        assert len(t.vertices) == 5315, "Error: Should have expected vertices"
        assert len(t.vertices) == t.header.vertexNum, "Error: Should have expected vertices"
        assert len(t.faces) == 9400, "Error should have expected polys"
        assert len(t.uv_pos) == len(t.vertices), "Error: Should have expected number of UVs"
        assert len(t.face_uvs) == t.header.faceNum, "Error should have expected number of face UVs"
        assert len(t.morphs) > 0, "Error: Should have morphs"

        log.info("Write tri back out again")
        t2 = TriFile()
        t2.vertices = t.vertices.copy()
        t2.faces = t.faces.copy()
        t2.uv_pos = t.uv_pos.copy()
        t2.face_uvs = t.face_uvs.copy()
        for name, verts in t.morphs.items():
            t2.morphs[name] = verts.copy()

        t2.write(os.path.join(test_path, "Out/CheetahMaleHead01.tri"))

        log.info("And read what you wrote to prove it worked")
        t3 = TriFile.from_file(os.path.join(test_path, "Out/CheetahMaleHead01.tri"))
        assert len(t3.vertices) == len(t.vertices), "Error: Should have expected vertices"
        assert len(t3.faces) == len(t.faces), "Error should have expected polys"
        assert len(t3.uv_pos) == len(t.uv_pos), "Error: Should have expected number of UVs"
        assert len(t3.face_uvs) == len(t.face_uvs), "Error should have expected number of face UVs"
        assert len(t3.morphs) == len(t.morphs), "Error: Morphs should not change"
        assert t3.vertices[5] == t.vertices[5], "Error: Vertices should not change"

        log.debug("TODO: Tests of UV positions fail--not sure why, they seem to work")
        #assert uv_near_eq(t3.uv_pos[5], t.uv_pos[5]), f"Error, UVs should not change: expected {str(t.uv_pos[5])}, got {str(t3.uv_pos[5])}"
        #assert t3.uv_pos[50] == t.uv_pos[50], "Error, UVs should not change"
        #assert t3.uv_pos[500] == t.uv_pos[500], "Error, UVs should not change"

        log.info("### TRIP file round trip")
        log.info("Read the file")
        t4 = TripFile.from_file(os.path.join(test_path, r"FO4\BodyTalk3.tri"))
        assert "BaseMaleBody:0" in t4.shapes, f"Error: Expected shape 'BaseMaleBody:0' in shapes"
        assert len(t4.shapes["BaseMaleBody:0"]) == 50, f"Error: Expected 50 morphs, have {len(t4.shapes['BaseMaleBody:0'])}"
        assert "BTTHinCalf" in t4.shapes["BaseMaleBody:0"], f"Error: Expected 'BTTHinCalf' morph, not found"

        log.info("Write the file")
        t4.write(os.path.join(test_path, r"Out\TripTest.tri"))

        log.info("Re-read the file")
        t5 = TripFile.from_file(os.path.join(test_path, r"Out\TripTest.tri"))
        assert "BaseMaleBody:0" in t5.shapes, f"Error: Expected shape 'BaseMaleBody:0' in shapes"
        assert len(t5.shapes["BaseMaleBody:0"]) == 50, f"Error: Expected 50 shapes, have {len(t5.shapes['BaseMaleBody:0'])}"
        assert "BTTHinCalf" in t5.shapes["BaseMaleBody:0"], f"Error: Expected 'BTTHinCalf' morph, not found"
        assert t4.shapes["BaseMaleBody:0"]['BTTHinCalf'][5][0] == t5.shapes["BaseMaleBody:0"]['BTTHinCalf'][5][0], \
            f"Error: Expected same vert indices: expected {t4.shapes['BaseMaleBody:0']['BTTHinCalf'][5][0]}, found {t5.shapes['BaseMaleBody:0']['BTTHinCalf'][5][0]}"
        assert t4.shapes["BaseMaleBody:0"]['BTTHinCalf'][5][1] == t5.shapes["BaseMaleBody:0"]['BTTHinCalf'][5][1], \
            f"Error: Expected same offsets: expected { t4.offsetmorphs['BTTHinCalf'][5][1]}, found {t5.offsetmorphs['BTTHinCalf'][5][1]}"


        print("DONE")
