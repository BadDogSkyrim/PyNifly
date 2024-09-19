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
import hashlib
from xmltools import XMLFile



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
        bone = self.arma.data.edit_bones.new(bonename)
        bone.matrix = xform

    
    def bones_from_xml(self, root):
        skel = root.find(".//*[@class='hkaSkeleton']")
        skelname = skel.find("./*[@name='name']").text
        parentIndices = [int(x) for x in skel.find("./*[@name='parentIndices']").text.split()]

        bonelist = []
        skelbones = skel.find("./*[@name='bones']")
        for b in skelbones.iter('hkobject'):
            bonelist.append(b.find("./*[@name='name']").text)

        pose = skel.find("./*[@name='referencePose']")
        poselist = pose.text.strip(' ()\t\n').split(')')

        # numseq = numseqpat.findall(pose.text)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        # for i in range(0, len(bonelist)):
        mxWorld = [Matrix.Identity(4)] * len(bonelist)
        i = j = 0
        while i < len(poselist) and j < len(bonelist):
            parent = None
            parentname = None
            if parentIndices[j] > 0:
                parentname = bonelist[parentIndices[j]]
                if parentname in self.arma.data.edit_bones:
                    parent = self.arma.data.edit_bones[parentname]

            loc = rot = None
            loclist = poselist[i].strip(' ()\t\n').split()
            if len(loclist) == 3:
                loc = Vector([float(x) for x in loclist])
            else:
                self.warn(f"Pose list does not have translation at index {j}: {poselist[i]}")

            # loc = Vector([float(x) for x in numseq[i*3].split()])
            # rotlist = [float(x) for x in numseq[i*3+1].split()]
            rotlist = poselist[i+1].strip(' ()\t\n').split()
            if len(rotlist) == 4:
                rot = Quaternion((float(rotlist[3]), float(rotlist[0]), float(rotlist[1]), float(rotlist[2])))
                rot.normalize()
            else:
                self.warn(f"Pose list does not have good rotation at index {j}: {poselist[i+1]}")
            # rot = Quaternion(rotlist[1:4], rotlist[0])
            scalelist = poselist[i+2].strip(' ()\t\n').split()
            if len(scalelist) == 3:
                scale = Vector([float(x) for x in scalelist])
            else:
                self.warn(f"Pose list does not have good scale at index {j}: {poselist[i+2]}")
            if loc and rot and scale:
                mxlocal = MatrixLocRotScale(loc, rot, scale)
                mx = mxlocal.copy()
                if parent:
                    mx = mxWorld[parentIndices[j]] @ mxlocal
                mxWorld[j] = mx
                new_bone = create_bone(self.arma.data, 
                                       bonelist[j], 
                                       mx, 
                                       "SKYRIM", 1.0, 0)
                new_bone.parent = parent
            i += 3
            j += 1
        
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.arma.update_from_editmode()


class ImportSkel(bpy.types.Operator, ImportHelper):
    """Import a skeleton XML file (unpacked from HXK)"""
    bl_idname = "import_scene.skeleton_xml"
    bl_label = "Import Skeleton XML"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".xml"
    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
    ) # type: ignore

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},) # type: ignore
    

    def execute(self, context):
        self.log_handler = LogHandler.New(bl_info, "IMPORT SKELETON", "XML")
        log.info(f"Importing {self.filepath}")
        try:
            infile = xml.parse(self.filepath)
            inroot = infile.getroot()
            sec1 = inroot[0]
            if inroot:
                arma = SkeletonArmature(Path(self.filepath).stem)
                arma.bones_from_xml(inroot)
                # arma.connect_armature(inroot)

            self.status = {'FINISHED'}

        except:
            self.log_handler.log.exception("Import of skeleton failed")
            self.report({"ERROR"}, "Import of skeleton failed, see console window for details")
            self.status = {'CANCELLED'}
        
        finally:
            self.log_handler.finish("IMPORT", self.filepath)

        return self.status


# ----------------------- EXPORT -------------------------------------

def set_param(elem, attribs, txt):
    p = xml.SubElement(elem, "hkparam")
    for n, v in attribs.items():
        p.set(n, v)
    p.text = txt
    return p


class ExportSkel(bpy.types.Operator, ExportHelper):
    """Export Blender armature to a skeleton XML file"""

    bl_idname = "export_scene.skeleton_xml"
    bl_label = 'Export skeleton XML'
    bl_options = {'PRESET'}

    filename_ext = ".xml"

    xmltree = None
    root = None
    section = None
    rootlevelcontainer = None
    animationcontainer = None
    memoryresourcecontainer = None
    skeleton = None
    block_index = 50
    context = None

    def use_index(self) -> int:
        v = self.block_index
        self.block_index += 1
        return v
    

    def find_root(self, bones):
        for b in bones:
            if b.parent not in bones:
                return b
        return bones[0]
    

    def find_parent(self, bone):
        """Find the parent of the given bone, skipping over any that are not
        in self.export_bones. Returns None if no such parent is found."""
        p = None
        bp = bone.parent
        while bp and not p:
            if bp in self.export_bones:
                p = bp
            bp = bp.parent
        return p


    def set_incr_name(self, elem):
        elem.set('name', "#{:04}".format(self.use_index()))


    def set_signature(self, elem, seed, strlist):
        h = hashlib.blake2b(seed.encode('utf-8'), digest_size=4)
        for s in strlist:
            h.update(s.encode('utf-8'))
        elem.set('signature', "0x" + h.hexdigest())


    def write_header(self) -> None:
        self.root = xml.Element('hkpackfile')
        self.root.set("classversion", "8")
        self.root.set("contentsversion", "hk_2010.2.0-r1")
        self.section = xml.SubElement(self.root, 'hksection')
        self.section.set("name", "__data__")
        self.xmltree = xml.ElementTree(self.root)

    def write_header_refs(self):
        self.root.set("toplevelobject", self.rootlevelcontainer.attrib["name"])


    def write_rootlevelcontainer(self):
        rlc = xml.SubElement(self.section, "hkobject")
        self.set_incr_name(rlc)
        rlc.set("class", "hkRootLevelContainer")
        self.set_signature(rlc, "hkRootLevelContainer", [])
        self.rootlevelcontainer = rlc

    def write_rootlevel_refs(self):
        v = set_param(self.rootlevelcontainer, {"name":"namedVariants", "numelements":"2"}, "")
        o1 = xml.SubElement(v, "hkobject")
        set_param(o1, {'name':"name"}, "Merged Animation Container")
        set_param(o1, {'name':"className"}, "hkaAnimationContainer")
        set_param(o1, {'name':"variant"}, self.animationcontainer.attrib['name'])
        o2 = xml.SubElement(v, "hkobject")
        set_param(o2, {'name':"name"}, "Resource Data")
        set_param(o2, {'name':"className"}, "hkMemoryResourceContainer")
        set_param(o2, {'name':"variant"}, self.memoryresourcecontainer.attrib['name'])


    def write_animationcontainer(self):
        e = xml.SubElement(self.section, "hkobject")
        self.set_incr_name(e)
        e.set("class", "hkaAnimationContainer")
        self.set_signature(e, "hkaAnimationContainer", [])
        self.animationcontainer = e

    def write_animationcontainer_refs(self):
        e = self.animationcontainer
        set_param(e, {"name":"skeletons", "numelements":"1"}, self.skeleton.attrib['name'])
        set_param(e, {"name":"animations", "numelements":"0"}, "")
        set_param(e, {"name":"bindings", "numelements":"0"}, "")
        set_param(e, {"name":"attachments", "numelements":"0"}, "")
        set_param(e, {"name":"skins", "numelements":"0"}, "")


    def write_parentindices(self, skel):
        pidx = []
        for b in self.export_bones:
            bp = self.find_parent(b)
            if bp:
                i = self.export_bones.index(bp) 
            else:
                i = -1
            pidx.append(i)

        set_param(skel, 
                  {"name":"parentIndices", "numelements":str(len(self.export_bones))},
                  " ".join(str(x) for x in pidx))


    def write_bones(self, skel):
        bonesparam = set_param(skel, 
                               {"name":"bones", "numelements":str(len(self.export_bones))}, 
                               "")

        for b in self.export_bones:
            obj = xml.SubElement(bonesparam, 'hkobject')
            set_param(obj, {"name":"name"}, b.name)
            set_param(obj, {"name":"lockTranslation"}, "false")


    def write_pose(self, skel):
        """Write bone poses to the referencePose element"""
        bones = self.export_bones
        adjust_mx = Matrix.Rotation(pi/2, 4, Vector([1,0,0]))
        adjust_mx = Matrix.Identity(4)
        txt = ""
        for b in bones:
            mx = b.matrix_local.copy()
            p = self.find_parent(b)
            if not p:
                # No parent being exported, this is top-level; export relative to the parent.
                p = b.parent
            if p:
                # px = adjust_mx @ b.parent.matrix
                px = p.matrix_local
                mx = px.inverted() @ mx

            xl = mx.translation
            xl.rotate(adjust_mx)
            txt += "({0:0.6f} {1:0.6f} {2:0.6f})".format(*xl)
            q = mx.to_quaternion()
            qax = q.axis
            qax.rotate(adjust_mx)
            txt += "({0:0.6f} {1:0.6f} {2:0.6f} {3:0.6f})".format(-q[1], q[3], -q[2], -q[0])
            s = mx.to_scale()
            txt += "({0:0.6f} {1:0.6f} {2:0.6f})\n".format(*s)

        set_param(skel, {'name':"referencePose", 'numelements':str(len(bones))}, txt)


    def write_skel(self) -> None:
        arma = self.context.object
        bones = [arma.data.bones[x.name] for x in arma.pose.bones if x.bone.select]
        self.export_bones = bones
        rootbone = self.find_root(bones)
        skel = xml.SubElement(self.section, 'hkobject')
        self.set_incr_name(skel)
        skel.set('class', "hkaSkeleton")
        self.set_signature(skel, "hkaSkeleton", [b.name for b in bones])
        set_param(skel, {"name":"name"}, rootbone.name)
        self.write_parentindices(skel)
        self.write_bones(skel)
        self.write_pose(skel)
        set_param(skel, {"name":"referenceFloats", "numelements":"0"}, "")
        set_param(skel, {"name":"floatSlots", "numelements":"0"}, "")
        set_param(skel, {"name":"localFrames", "numelements":"0"}, "")
        self.skeleton = skel


    def write_memoryresourcecontainer(self):
        e = xml.SubElement(self.section, "hkobject")
        self.set_incr_name(e)
        e.set("class", "hkMemoryResourceContainer")
        self.set_signature(e, "hkMemoryResourceContainer", [])
        set_param(e, {"name":"name"}, "")
        set_param(e, {"name":"resourceHandles", "numelements":"0"}, "")
        set_param(e, {"name":"children", "numelements":"0"}, "")
        self.memoryresourcecontainer = e


    def save(self, filepath=None):
        """Write the XML to a file"""
        self.xmltree.write(filepath if filepath else self.filepath,
                           xml_declaration=True,
                           encoding='utf-8')


    def do_export(self):
        self.write_header()
        self.write_rootlevelcontainer()
        self.write_animationcontainer()
        self.write_skel()
        self.write_memoryresourcecontainer()
        self.write_header_refs()
        self.write_rootlevel_refs()
        self.write_animationcontainer_refs()
        self.save()
        log.info(f"Wrote {self.filepath}")
    

    def execute(self, context):
        self.log_handler = LogHandler.New(bl_info, "EXPORT SKELETON", "XML")

        try:
            self.context = context
            self.do_export()

            self.status = {'FINISHED'}

        except:
            self.log_handler.log.exception("Export of skeleton failed")
            self.report({"ERROR"}, "Export failed, see console window for details")
            self.status = {'CANCELLED'}
        
        finally:
            self.log_handler.finish("EXPORT", self.filepath)

        return self.status

    @classmethod
    def poll(cls, context):
        if not context.object:
            log.error("Must have an active object to export.")
            return False
        
        if context.object.mode != 'POSE':
            log.debug("Must be in POSE Mode to export skeleton bones")
            return False

        try:
            if len([x for x in context.object.pose.bones if x.bone.select]) == 0:
                log.debug("Must select one or more bones in pose mode to export")
                return False
        except:
            log.debug("Must have a selected armature with selected bones.")
            return False
        
        return True
    

# -------------------- REGISTER/UNREGISTER --------------------------

def nifly_menu_import_skel(self, context):
    self.layout.operator(ImportSkel.bl_idname, text="Skeleton file (.xml)")

def nifly_menu_export_skel(self, context):
    self.layout.operator(ExportSkel.bl_idname, text="Skeleton file (.xml)")

skel_registry = [('i', nifly_menu_import_skel, ImportSkel), 
                 ('e', nifly_menu_export_skel, ExportSkel)]

def unregister():
    for d, f, c in skel_registry:
        try:
            if d == 'i':
                bpy.types.TOPBAR_MT_file_import.remove(f)
            else:
                bpy.types.TOPBAR_MT_file_export.remove(f)
        except: 
            pass
        try:
            bpy.utils.unregister_class(c) 
        except:
            pass


def register():
    for d, f, c in skel_registry:
        try:
            bpy.utils.register_class(c)
        except:
            pass
        try:
            if d == 'i':
                bpy.types.TOPBAR_MT_file_import.append(f)
            else:
                bpy.types.TOPBAR_MT_file_export.append(f)
        except:
            pass

if __name__ == "__main__":
    unregister()
    register()
