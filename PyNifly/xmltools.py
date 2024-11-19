"""Tools for manipulating XML files"""    

import os
import shutil
import tempfile
import subprocess
import logging
import xml.etree.ElementTree as xml
import niflytools

hkxcmd_path = ""


class XMLFile:
    """A XMLFile can be loaded from an XML text file or a HKX compressed file. If
    given a HKX file it is converted to XML.
    """
    _hkxcmd_path = None

    @classmethod
    def SetPath(cls, filepath):
        """Set the filepath to use for hkxcmd.exe"""
        XMLFile._hkxcmd_path = filepath

    
    def __init__(self, filepath=None, logger=None):
        self.file = None
        self.root = None
        self.hkx_filepath = None
        self.xml_filepath = None
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger("pynifly")
        if filepath:
            self.open(filepath)


    @classmethod
    def hkx_to_xml(cls, filepath):
        """Given a HKX file, convert it to XML and return the XML filepath."""
        log = logging.getLogger("pynifly")
        # Putting a copy of the input file in the temporary directory because HKXCMD seems
        # to want input and output together.
        tmp_filepath = niflytools.tmp_copy(filepath)
        xml_filepath = niflytools.tmp_filepath(filepath, ext=".xml")

        if not xml_filepath:
            raise RuntimeError(f"Could not create temporary XML filepath for {filepath}")
                
        log.debug(f"HKXCMD CONVERT -V:XML {tmp_filepath} {xml_filepath}")
        stat = subprocess.run([cls._hkxcmd_path, 
                                "CONVERT", 
                                "-V:XML",
                                tmp_filepath, 
                                xml_filepath], 
                                capture_output=True, 
                                check=True)
        
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            raise RuntimeError(f"HKXCMD failed with {s}")
        
        if not os.path.exists(xml_filepath):
            raise RuntimeError(f"Failed to create {xml_filepath}")

        return xml_filepath
    

    @classmethod
    def xml_to_hkx(cls, filepath_in, filepath_out):
        """
        Given a XML file, convert it to a HKX file at the given path.
        """
        # Make a copy of the xml file that is guaranteed not to have spaces in the path.
        xml_filepath = niflytools.nospace_filepath(filepath_in)
        hkx_filepath = niflytools.nospace_filepath(filepath_out, ".hkx")


        niflytools.log.info(f"HKXCMD CONVERT -V:WIN32 {xml_filepath} {hkx_filepath}")
        stat = subprocess.run([cls._hkxcmd_path, 
                                "CONVERT", 
                               "-V:WIN32",
                                xml_filepath, 
                                hkx_filepath], 
                                capture_output=True, check=True)
        
        if stat.returncode:
            s = stat.stderr.decode('utf-8').strip()
            niflytools.log.error("Could not create HKX file")
            raise Exception(s)
        
        if not os.path.exists(hkx_filepath):
            raise Exception(f"Failed to create {hkx_filepath}")

        niflytools.log.info(f"Wrote {hkx_filepath}")
        if hkx_filepath != filepath_out:
            niflytools.copyfile(hkx_filepath, filepath_out)
            niflytools.log.info(f"Wrote {filepath_out}")
    

    def open(self, filepath):
        """
        Open the file. If it's a HKX file, convert to XML first.
        Sets:

        - self.hkx_filepath -- if filepath is a HKX file, we create a temporary copy with
          short names that hkxcmd can operate on.
        - self.file -- the file object for the XML parser
        - self.root -- the XML parser root
        """
        ext = os.path.splitext(filepath)[1].upper()
        if ext == ".XML":
            fp = filepath
        elif ext == ".HKX":
            self.hkx_filepath = niflytools.tmp_filepath(filepath)
            niflytools.copyfile(filepath, self.hkx_filepath)
            fp = XMLFile.hkx_to_xml(self.hkx_filepath)
            self.logger.info(f"Temporary xml file created: {fp}")
        else:
            raise ValueError("Need either a XML or HKX file.")
        
        self.xml_filepath = fp
        self.file = xml.parse(fp)
        self.root = self.file.getroot()
        

    @property
    def contains_skeleton(self):
        skel = self.root.find(".//*[@class='hkaSkeleton']")
        return skel is not None
    

    @property
    def contains_animation(self):
        anim = self.root.find(".//*[@class='hkaSplineCompressedAnimation']")
        return anim is not None

            
# def execute(self, context):
#         LogStart(bl_info, "IMPORT SKELETON", "XML")
#         log.info(f"Importing {self.filepath}")
#         infile = xml.parse(self.filepath)
#         inroot = infile.getroot()
#         log.debug(f"Root tag: {inroot.tag}")
#         log.debug(f"Root attributes: {inroot.attrib}")
#         log.debug(f"Children: {[x.attrib for x in inroot]}")
#         sec1 = inroot[0]
#         log.debug(f"First section: {sec1.attrib}")
#         if inroot:
#             arma = SkeletonArmature(Path(self.filepath).stem)
#             arma.bones_from_xml(inroot)
#             # arma.connect_armature(inroot)

#         status = {'FINISHED'}

#         return status
