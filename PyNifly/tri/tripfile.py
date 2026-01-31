"""
.tri file handling for bodyslide/outfit studio TRIP files
"""

import os
import logging
from struct import (unpack, pack)
from typing import BinaryIO

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


def is_trip(file):
    """ Peek at the file header to see if it is a TRIP file. """
    data = file.read(4)
    file.seek(0)
    return (data == b'PIRT' or data == b'\0IRT')


class TripFile:
    def __init__(self, filepath:str=None):
        self.filepath = filepath
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
    def from_file(cls, file:BinaryIO):
        tri = TripFile(filepath=file.name)
        tri.read(file)
        return tri
    
