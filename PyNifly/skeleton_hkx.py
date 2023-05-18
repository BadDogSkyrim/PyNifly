"""Skeleton XML export/import for Blender"""

# Copyright © 2023, Bad Dog.

import bpy
import bpy_types
from bpy.props import (
        BoolProperty,
        CollectionProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper)
from blender_defs import *
import xml.etree.ElementTree as xml

bl_info = {
    "name": "NIF format",
    "description": "Nifly Import/Export for Skyrim, Skyrim SE, and Fallout 4 NIF files (*.nif)",
    "author": "Bad Dog",
    "blender": (3, 0, 0),
    "version": (9, 6, 2),  
    "location": "File > Import-Export",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

numseqpat = re.compile("[\d\.\s-]+")
numberpat = re.compile("[\d\.-]+")

class SkeletonArmature():
    def __init__(self, name):
        """Make an armature to import a skeleton XML into. 
        Returns the armature, selected and active."""
        armdata = bpy.data.armatures.new(name)
        self.arma = bpy.data.objects.new(name, armdata)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(self.arma)
        ObjectActive(self.arma)
        ObjectSelect([self.arma])


    def addbone(self, bonename, xform):
        """Create the bone in the armature. Assume armature is in edit mode."""
        log.debug(f"Adding bone {bonename} at \n{xform}")
        bone = self.arma.data.edit_bones.new(bonename)
        bone.matrix = xform

    
    def bones_from_xml(self, root):
        skel = root.find(".//*[@class='hkaSkeleton']")
        skelname = skel.find("./*[@name='name']").text
        skelindices = [int(x) for x in skel.find("./*[@name='parentIndices']").text.split()]
        log.debug(f"Skeleton name = {skelname}")
        log.debug(f"Skeleton indices = {skelindices}")

        bonelist = []
        skelbones = skel.find("./*[@name='bones']")
        for b in skelbones.iter('hkobject'):
            bonelist.append(b.find("./*[@name='name']").text)
        log.debug(f"Found bones {bonelist}")

        pose = skel.find("./*[@name='referencePose']")
        numseq = numseqpat.findall(pose.text)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        for i in range(0, len(bonelist)):
            log.debug(f"[{i}]")
            loc = Vector([float(x) for x in numseq[i*3].split()])
            rotlist = [float(x) for x in numseq[i*3+1].split()]
            rot = Quaternion(rotlist[1:4], rotlist[0])
            scale = Vector([float(x) for x in numseq[i*3+2].split()])
            log.debug(f"Location: {loc}")
            log.debug(f"Rotation: {rot}")
            log.debug(f"Scale: {scale}")
            create_bone(self.arma.data, bonelist[i], Matrix.LocRotScale(loc, rot, scale), 
                        "SKYRIM", 1.0, 0)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.arma.update_from_editmode()


class ImportSkel(bpy.types.Operator, ImportHelper):
    """Import a skeleton XML file (unpacked from HXK)"""
    bl_idname = "import_scene.skeleton_hkx"
    bl_label = "Import Skeleton HKX (XML)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".xml"
    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},)
    

    def execute(self, context):
        LogStart(bl_info, "IMPORT SKELETON", "XML")
        log.info(f"Importing {self.filepath}")
        infile = xml.parse(self.filepath)
        inroot = infile.getroot()
        log.debug(f"Root tag: {inroot.tag}")
        log.debug(f"Root attributes: {inroot.attrib}")
        log.debug(f"Children: {[x.attrib for x in inroot]}")
        sec1 = inroot[0]
        log.debug(f"First section: {sec1.attrib}")
        if inroot:
            arma = SkeletonArmature(Path(self.filepath).stem)
            arma.bones_from_xml(inroot)

        status = {'FINISHED'}

        return status


# ----------------------- EXPORT -------------------------------------

class ExportSkel(bpy.types.Operator, ExportHelper):
    """Export Blender armature to a skeleton HKX file"""

    bl_idname = "export_scene.skeleton_hkx"
    bl_label = 'Export skeleton HKX (XML)'
    bl_options = {'PRESET'}

    filename_ext = ".xml"

    xmltree = None
    root = None

    def write_header(self) -> None:
        self.root = xml.Element('hkpackfile')
        sec = xml.SubElement(self.root, 'hksection')
        skel = xml.SubElement(sec, 'hkobject')
        self.xmltree = xml.ElementTree(self.root)


    def save(self, filepath=None):
        """Write the XML to a file"""
        log.debug(f"Writing to file: {xml.tostring(self.root)}")
        self.xmltree.write(filepath if filepath else self.filepath,
                           xml_declaration=True)


    def execute(self, context):
        LogStart(bl_info, "EXPORT SKELETON", "XML")

        self.write_header()
        self.save()
        log.info(f"Wrote {self.filepath}")

        status = {'FINISHED'}
        return status
    

    @classmethod
    def poll(cls, context):
        if context.object.mode != 'POSE':
            log.error("Must be in POSE Mode to export skeleton bones")
            return False

        try:
            if len([x for x in context.object.pose.bones if x.bone.select]) == 0:
                log.error("Must select one or more bones in pose mode to export")
                return False
        except:
            log.error("Must have a selected armature with selected bones.")
            return False
        
        return True
    

# -------------------- REGISTER/UNREGISTER --------------------------

def nifly_menu_import_skel(self, context):
    self.layout.operator(ImportSkel.bl_idname, text="Skeleton file (.xml)")
def nifly_menu_export_skel(self, context):
    self.layout.operator(ExportSkel.bl_idname, text="Skeleton file (.xml)")

def unregister():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(nifly_menu_import_skel)
        bpy.types.TOPBAR_MT_file_export.remove(nifly_menu_export_skel)
        bpy.utils.unregister_class(ImportSkel)
        bpy.utils.unregister_class(ExportSkel)
    except:
        pass

def register():
    unregister()
    bpy.types.TOPBAR_MT_file_import.append(nifly_menu_import_skel)
    bpy.types.TOPBAR_MT_file_export.append(nifly_menu_export_skel)
    bpy.utils.register_class(ImportSkel)
    bpy.utils.register_class(ExportSkel)
