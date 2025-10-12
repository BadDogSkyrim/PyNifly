""" niflytools

    Utility functions and classes to support import/export
    Includes game-specific mesh information

"""

import os
import time
import logging
import re
import tempfile
import shutil
from pathlib import Path


logging.basicConfig(encoding='utf-8', level=logging.DEBUG)
log = logging.getLogger("pynifly")
log.setLevel(logging.INFO)
    

# ###################### FILE HANDLING ##################################

def tmp_filepath(filepath, ext=None):
    """Return a unique temporary filename. Name is based on the base name of 
    'filepath', with suffixes to make it unique, and given the extension 'ext'.
    """
    base_ext = os.path.basename(filepath)
    basename, extension = os.path.splitext(base_ext)
    name = basename.replace(' ', '_')
    if not name.startswith("tmp_"): name = "tmp_" + name
    if not ext: ext = extension

    fpbase = os.path.join(tempfile.gettempdir(), name)
    i = 0
    iter = ""
    fp = ""
    while i < 10000:
        iter = f"_{(int(time.time()*1000) & 0xFFFFFF):06X}"
        fp = fpbase + iter + ext
        if not os.path.exists(fp): break
        i += 1
    if i < 10000: 
        return fp
    else:
        raise Exception("Could not create temporary file")
    

def nospace_filepath(filepath, ext=None):
    """
    Return the input filepath if no spaces, else a new temp filepath.
    Also remove any surrounding quotes.
    """
    fp = filepath.strip('"').strip("'")
    try:
        n = fp.index(' ')
        return tmp_filepath(fp, ext=ext)
    except ValueError:
        pass

    if ext is not None:
        bn, e = os.path.splitext(fp)
        if not e:
            fp = bn + ext
    return fp


def copyfile(fin, fout):
    fin_clean = fin.strip('"')
    if fin_clean != fout:
        shutil.copy(fin_clean, fout)


def tmp_copy(filepath) -> str:
    """Create a temporary copy of the file and return its filepath."""
    fp = tmp_filepath(filepath)
    copyfile(filepath, fp)
    return fp


def tmp_copy_nospace(filepath) -> str:
    """
    If the filepath contains spaces, create a temporary copy of the file and return its
    filepath. Otherwise just return the original.
    """
    try:
        n = filepath.index(' ')
        fp = tmp_filepath(filepath)
        copyfile(filepath, fp)
        return fp
    except:
        pass
    return filepath


def extend_filenames(root, separator, files=None):
    """ Extend the given relative path names with the portion of the root before the
        separator. 

        If there are no files, just return the portion of the root before the separator.
        
        * root = absolute filepath 
        * separator = Folder within the filepath. The part before the separator is the
          common directory path to use for the files. If None, use the entire root.  
        * files = list of relative file paths 
        """
    rootpath = Path(root)
    if separator:
        uppersep = separator.upper()
        upperpath = [s.upper() for s in rootpath.parts]
        sharedpart = rootpath.parent
        if uppersep in upperpath:
            seploc = upperpath.index(uppersep)
            sharedpart = rootpath.parents[len(rootpath.parts) - seploc - 1]
    else:
        sharedpart = rootpath
    if files:
        return [(str(sharedpart / f) if len(f) > 0 else "") for f in files]
    else:
        return str(sharedpart)
    

def find_referenced_file(filepath:str, nifpath:str, root='textures', alt_suffix=None, alt_path=None) -> str:
    """
    Look for a texture file with either a PNG or DDS extension.
    filepath may or may not be absolute. If relative, may or may not start with "textures".
    if relative, look in basedir/textures. If not there, look in blender's texture directory.
    Look for both the dds and png extension.
    Return the path if found, else None.
    """
    fp = Path(filepath.lower())

    # If relative, must start with "textures"
    if (not fp.is_absolute()) and fp.parts[0] != root:
        fp = Path(root) / fp
    
    # If fp is absolute, check for DDS or PNG variant and return whichever exists
    if fp.is_absolute():
        if alt_suffix and fp.with_suffix(alt_suffix).exists():
            return str(fp.with_suffix(alt_suffix))
        if fp.exists():
            return str(fp)
        # Absolute path not found, treat path as relative
        fp = Path(*fp.parts[fp.parts.index(root):])

    # If relative, look in nifpath first
    bd = Path(nifpath.lower())
    if 'meshes' in bd.parts:
        bd = Path(*bd.parts[:bd.parts.index('meshes')])
        fullp = bd / fp
        if alt_suffix and fullp.with_suffix(alt_suffix).exists():
            return str(fullp.with_suffix(alt_suffix))
        if fullp.exists():
            return str(fullp)
        
    # Not found, look in alternative texture directory
    if alt_path:
        bd = Path(alt_path.lower())
        if root in bd.parts:
            bd = Path(*bd.parts[:bd.parts.index(alt_suffix)-1])
        fullp = bd / fp
        if alt_suffix and fullp.with_suffix(alt_suffix).exists():
            return str(fullp.with_suffix(alt_suffix))
        if fullp.exists():
            return str(fullp)
    return None


def replace_extensions(files, orig, rep):
    """ Replace the extension of files in the given list """
    return [re.sub(orig, rep, f, flags=re.I) for f in files]


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
    return [x for x in files if x != '' and not os.path.exists(x)]


def truncate_filename(filepath: str, root_dir: str)-> str:
    """Truncate the initial part of a filepath up to the given root (e.g. 'meshes'). """
    n = filepath.lower().find(root_dir.lower())
    if n < 0:
        return filepath
    else:
        return filepath[(n+len(root_dir)+1):]


def find_tris(nif):
    """
        Return a list of tri files associated with the given nif, if any.

        if nif filepath = fn.ext: return
            fn.tri
            fnchargen.tri
            fn_chargen.tri
    """
    trifiles = []
    fp = Path(nif.filepath)

    ftri = fp.with_suffix(".tri")
    if ftri.exists():
        trifiles.append(ftri)

    fchar = ftri.with_stem(fp.stem + 'chargen')
    if fchar.exists():
        trifiles.append(fchar)
    else:
        fchar = ftri.with_stem(fp.stem + '_chargen')
        if fchar.exists():
            trifiles.append(fchar)

    return trifiles
        

def find_trip(nif):
    """
        Return the trip file associated with the given nif, if any.
    """
    fp = Path(nif.filepath)

    for v in [s[1] for s in nif.string_data if s[0] == 'BODYTRI']:
        f = extend_filenames(nif.filepath, 'meshes', [os.path.join('meshes', v)])
        fp = Path(f[0])
        if fp.exists():
            return fp

    return None
        


# ###################### OTHER STUFF ##################################

def find_object(name, coll, fn=lambda x: x):
    """Find an object by name with the given list of objects
        name = name to find. Blocks in nifs aren't supposed to have the same
            name but sometimes they do. Also, a Blend file might contain imports from several nifs. 
            So we can't be sure the Blender name is exactly the name in the nif. Blender may have 
            appended .### to it, where ### is some number to make it unique.
        coll = list or dictionary of objects
        fn = function to return the name from an object in the collection. Default is for when
            the collection is just a list of names.
        Return = object from list, or None. Object either has the exact name or the name followed 
            by .###
    """
    foundobj = None
    for obj in coll:
        n = fn(obj)
        # Exact matches always take precedence
        if n == name:
            foundobj = obj
            break
        if re.search(name + r'\.\d\d\d', n):
            foundobj = obj
            break
    return foundobj


def trim_blender_suffix(s):
    """Remove Blender's ".###" suffix, if any"""
    m = re.search(r"(.+)\.\d\d\d", s)
    if m:
        return m.groups()[0]
    else:
        return s


def uv_location(uv):
    """ Rounds UV location to eliminate floating point error """
    return (round(uv[0], 4), round(uv[1], 4))


def NearEqual(n1, n2, epsilon=0.001):
    return abs(n1-n2) < epsilon


def VNearEqual(v1, v2, epsilon=0.001):
    r = True
    for a, b in zip(v1, v2):
        r = r and (abs(a-b) < epsilon)
    return r

def MatNearEqual(m1, m2, epsilon=0.001):
    """Compare matrices for near-equality.
    Matrix must act like a list of lists.
    """
    r = True
    for a, b in zip(m1, m2):
        r = r and VNearEqual(a, b, epsilon)
    return r


def XFNearEqual(x1, x2, epsilon=0.001):
    return VNearEqual(x1.translation, x2.translation, epsilon) \
        and MatNearEqual(x1.rotation, x2.rotation, epsilon) \
        and NearEqual(x1.scale, x2.scale, epsilon)


def QNearEqual(q1, q2, epsilon=0.001):
    return NearEqual(abs(q1.dot(q2)), 1.0, epsilon=epsilon)


def all_equal(the_list):
    """Determine whether all the values in the list are the same:
    [A, B, C] -> A == B == C
    """
    if the_list:
        return the_list[:-1] == the_list[1:]
    return True


def all_NearEqual(the_list, epsilon=0.001):
    if the_list:
        a = the_list[0]
        for b in the_list[1:]:
            if not NearEqual(a, b, epsilon=epsilon):
                return False
    return True


def vert_uv_key(vert_index, uv):
    return str(vert_index) + "_" + str(uv)


def mesh_split_by_uv(verts, loops, norms, uvmap, weights, morphdict):
    """Split a mesh represented by parameters and split verts if necessary because it
        (1) maps to 2 UV locations or (2) has split normals.
        verts = [(x, y, z), ...] vertex locations
        norms = [(x, y, z), ...] normals 1:1 with loops
        loops = [int, ...] blender-style loops--elements are indices into verts. 
            Loops are already triangularized so they are in triples, tho the list is flat
        uvmap = [(u, v), ...] uvmap--matches 1:1 with loops
        weights = [dict[group-name: weight], ...] vertex weights, 1:1 with verts
        morphdict = {morph-name: [(x,y,z)...], ...} vertex list for each morph
    Returns
        verts = extended with additional verts where splits were required
        norms = not changed. Future: If we decide to split the mesh on sharp edges, may be modified.
        loops = modified to reference the new verts where needed 
        uvmap = not changed
        weights = extended to match verts
    """
    # Walk the loops. If the associated UV puts the vert in a new location, dup the vert
    vert_uvs = [None] * len(verts) # found UV locations of verts
    #vert_norms = [(0.0, 0.0, 0.0)] * len(verts) # found normals of verts
    change_table = {} # {old_vert_index: new_vert_index}
    for i, vert_idx in enumerate(loops):
        this_vert_loc = uv_location(uvmap[i])
        #this_vert_norm = norms[i]
        if vert_uvs[vert_idx] is None:
            # Not given this vert a location yet
            vert_uvs[vert_idx] = this_vert_loc
            #vert_norms[vert_idx] = this_vert_norm
        elif vert_uvs[vert_idx] != this_vert_loc: # or not VNearEqual(this_vert_norm, vert_norms[vert_idx]):
            # Found already at different location or with different normal
            vert_key = vert_uv_key(vert_idx, this_vert_loc)
            if vert_key in change_table:
                loops[i] = change_table[vert_key]
            else:
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
    def __init__(self, blender_name, nif_name, parent=None, niftools_name=None):
        self.blender = blender_name
        self.nif = nif_name
        self.niftools = niftools_name
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
    def __init__(self, bone_list, morph_list, part_list, dismem_list=[], use_niftools=False):
        self.byNif = {}
        self.byPynifly = {}
        self.byNiftools = {}
        self.parts = {}
        self.dismem = {}

        for b in bone_list:
            self.byNif[b.nif] = b
            self.byPynifly[b.blender] = b

        for b in bone_list:
            if b.parent_name in self.byPynifly:
                b.parent = self.byPynifly[b.parent_name]

        self.use_niftools = use_niftools # Call our own property to set up dicts

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

    @property
    def use_niftools(self):
        return self._use_niftools

    @use_niftools.setter
    def use_niftools(self, val):
        self._use_niftools = val
        if val:
            for b in self.byNif.values():
                self.byNiftools[b.niftools] = b
            self.active_dict = self.byNiftools
        else:
            self.active_dict = self.byPynifly

    def blender_name(self, nif_name):
        if self.use_niftools:
            if nif_name in self.byNif:
                return self.byNif[nif_name].niftools
        else:
            if nif_name in self.byNif:
                return self.byNif[nif_name].blender
        return nif_name
    
    def nif_name(self, blender_name):
        if blender_name in self.active_dict:
            return self.active_dict[blender_name].nif
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
        return len(boneset.intersection(set(self.active_dict.keys()))) + \
            len(boneset.intersection(set(self.byNif.keys())))

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
# PyNifly, Vanilla, NifTools, Parent
SkeletonBone('Bip01',  'Bip01',   None, ),
SkeletonBone('Bip01 NonAccum',  'Bip01 NonAccum',   'Bip01', ),
SkeletonBone('Bip01 Pelvis',  'Bip01 Pelvis',   'Bip01 NonAccum', ),
SkeletonBone('Bip01 Thigh.L',  'Bip01 L Thigh',   'Bip01 Pelvis', ),
SkeletonBone('Bip01 Calf.L',  'Bip01 L Calf',   'Bip01 Thigh.L', ),
SkeletonBone('Bip01 Foot.L',  'Bip01 L Foot',   'Bip01 Calf.L', ),
SkeletonBone('Bip01 Toe0.L',  'Bip01 L Toe0',   'Bip01 Foot.L', ),
SkeletonBone('Bip01 Thigh.R',  'Bip01 R Thigh',   'Bip01 Pelvis', ),
SkeletonBone('Bip01 Calf.R',  'Bip01 R Calf',   'Bip01 Thigh.R', ),
SkeletonBone('Bip01 Foot.R',  'Bip01 R Foot',   'Bip01 Calf.R', ),
SkeletonBone('Bip01 Toe0.R',  'Bip01 R Toe0',   'Bip01 Foot.R', ),
SkeletonBone('Bip01 GenHelper',  'Bip01 GenHelper',   'Bip01 Pelvis', ),
SkeletonBone('Bip01 Penis01',  'Bip01 Penis01',   'Bip01 GenHelper', ),
SkeletonBone('Bip01 Penis02',  'Bip01 Penis02',   'Bip01 Penis01', ),
SkeletonBone('Bip01 Penis03',  'Bip01 Penis03',   'Bip01 Penis02', ),
SkeletonBone('Bip01 Penis04',  'Bip01 Penis04',   'Bip01 Penis03', ),
SkeletonBone('Bip01 Penis05',  'Bip01 Penis05',   'Bip01 Penis04', ),
SkeletonBone('Bip01 Penis06',  'Bip01 Penis06',   'Bip01 Penis05', ),
SkeletonBone('Bip01 Scrotum01',  'Bip01 Scrotum01',   'Bip01 GenHelper', ),
SkeletonBone('Bip01 Scrotum02',  'Bip01 Scrotum02',   'Bip01 Scrotum01', ),
SkeletonBone('Dick1',  'Dick1',   'Bip01 Pelvis', ),
SkeletonBone('Dick2',  'Dick2',   'Dick1', ),
SkeletonBone('Dick3',  'Dick3',   'Dick2', ),
SkeletonBone('Dick4',  'Dick4',   'Dick3', ),
SkeletonBone('Balls',  'Balls',   'Bip01 Pelvis', ),
SkeletonBone('vagina.R',  'vagina.R',   'Bip01 Pelvis', ),
SkeletonBone('vagina.L',  'vagina.L',   'Bip01 Pelvis', ),
SkeletonBone('Bip01 Spine',  'Bip01 Spine',   'Bip01 NonAccum', ),
SkeletonBone('Bip01 Spine1',  'Bip01 Spine1',   'Bip01 Spine', ),
SkeletonBone('Bip01 Spine2',  'Bip01 Spine2',   'Bip01 Spine1', ),
SkeletonBone('Bip01 Neck',  'Bip01 Neck',   'Bip01 Spine2', ),
SkeletonBone('Bip01 Neck1',  'Bip01 Neck1',   'Bip01 Neck', ),
SkeletonBone('Bip01 Head',  'Bip01 Head',   'Bip01 Neck1', ),
SkeletonBone('HeadAnims',  'HeadAnims',   'Bip01 Head', ),
SkeletonBone('Bip01 HT',  'Bip01 HT',   'Bip01 Head', ),
SkeletonBone('Bip01 HT2',  'Bip01 HT2',   'Bip01 HT', ),
SkeletonBone('Bip01 Tongue01',  'Bip01 Tongue01',   'Bip01 HT2', ),
SkeletonBone('Bip01 Tongue02',  'Bip01 Tongue02',   'Bip01 Tongue01', ),
SkeletonBone('Bip01 Tongue03',  'Bip01 Tongue03',   'Bip01 Tongue02', ),
SkeletonBone('Bip01 NVG',  'Bip01 NVG',   'Bip01 Head', ),
SkeletonBone('Bip01 NVG1',  'Bip01 NVG1',   'Bip01 NVG', ),
SkeletonBone('Bip01 NVG2',  'Bip01 NVG2',   'Bip01 NVG1', ),
SkeletonBone('Bip01 Clavicle.L',  'Bip01 L Clavicle',   'Bip01 Neck', ),
SkeletonBone('Bip01 UpperArm.L',  'Bip01 L UpperArm',   'Bip01 Clavicle.L', ),
SkeletonBone('Bip01 UpArmTwistBone.L',  'Bip01 LUpArmTwistBone',   'Bip01 UpperArm.L', ),
SkeletonBone('Bip01 Forearm.L',  'Bip01 L Forearm',   'Bip01 UpperArm.L', ),
SkeletonBone('Bip01 ForeTwist.L',  'Bip01 L ForeTwist',   'Bip01 Forearm.L', ),
SkeletonBone('Bip01 Hand.L',  'Bip01 L Hand',   'Bip01 Forearm.L', ),
SkeletonBone('Bip01 Thumb1.L',  'Bip01 L Thumb1',   'Bip01 Hand.L', ),
SkeletonBone('Bip01 Thumb11.L',  'Bip01 L Thumb11',   'Bip01 Thumb1.L', ),
SkeletonBone('Bip01 Thumb12.L',  'Bip01 L Thumb12',   'Bip01 Thumb11.L', ),
SkeletonBone('Bip01 Finger1.L',  'Bip01 L Finger1',   'Bip01 Hand.L', ),
SkeletonBone('Bip01 Finger11.L',  'Bip01 L Finger11',   'Bip01 Finger1.L', ),
SkeletonBone('Bip01 Finger12.L',  'Bip01 L Finger12',   'Bip01 Finger11.L', ),
SkeletonBone('Bip01 Finger2.L',  'Bip01 L Finger2',   'Bip01 Hand.L', ),
SkeletonBone('Bip01 Finger21.L',  'Bip01 L Finger21',   'Bip01 Finger2.L', ),
SkeletonBone('Bip01 Finger22.L',  'Bip01 L Finger22',   'Bip01 Finger21.L', ),
SkeletonBone('Bip01 Finger3.L',  'Bip01 L Finger3',   'Bip01 Hand.L', ),
SkeletonBone('Bip01 Finger31.L',  'Bip01 L Finger31',   'Bip01 Finger3.L', ),
SkeletonBone('Bip01 Finger32.L',  'Bip01 L Finger32',   'Bip01 Finger31.L', ),
SkeletonBone('Bip01 Finger4.L',  'Bip01 L Finger4',   'Bip01 Hand.L', ),
SkeletonBone('Bip01 Finger41.L',  'Bip01 L Finger41',   'Bip01 Finger4.L', ),
SkeletonBone('Bip01 Finger42.L',  'Bip01 L Finger42',   'Bip01 Finger41.L', ),
SkeletonBone('Bip01 Clavicle.R',  'Bip01 R Clavicle',   'Bip01 Neck', ),
SkeletonBone('Bip01 UpperArm.R',  'Bip01 R UpperArm',   'Bip01 Clavicle.R', ),
SkeletonBone('Bip01 UpArmTwistBone.R',  'Bip01 RUpArmTwistBone',   'Bip01 UpperArm.R', ),
SkeletonBone('Bip01 Forearm.R',  'Bip01 R Forearm',   'Bip01 UpperArm.R', ),
SkeletonBone('Bip01 ForeTwist.R',  'Bip01 R ForeTwist',   'Bip01 Forearm.R', ),
SkeletonBone('Bip01 Hand.R',  'Bip01 R Hand',   'Bip01 Forearm.R', ),
SkeletonBone('Weapon',  'Weapon',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Thumb1.R',  'Bip01 R Thumb1',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Thumb11.R',  'Bip01 R Thumb11',   'Bip01 Thumb1.R', ),
SkeletonBone('Bip01 Thumb12.R',  'Bip01 R Thumb12',   'Bip01 Thumb11.R', ),
SkeletonBone('Bip01 Finger1.R',  'Bip01 R Finger1',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Finger11.R',  'Bip01 R Finger11',   'Bip01 Finger1.R', ),
SkeletonBone('Bip01 Finger12.R',  'Bip01 R Finger12',   'Bip01 Finger11.R', ),
SkeletonBone('Bip01 Finger2.R',  'Bip01 R Finger2',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Finger21.R',  'Bip01 R Finger21',   'Bip01 Finger2.R', ),
SkeletonBone('Bip01 Finger22.R',  'Bip01 R Finger22',   'Bip01 Finger21.R', ),
SkeletonBone('Bip01 Finger3.R',  'Bip01 R Finger3',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Finger31.R',  'Bip01 R Finger31',   'Bip01 Finger3.R', ),
SkeletonBone('Bip01 Finger32.R',  'Bip01 R Finger32',   'Bip01 Finger31.R', ),
SkeletonBone('Bip01 Finger4.R',  'Bip01 R Finger4',   'Bip01 Hand.R', ),
SkeletonBone('Bip01 Finger41.R',  'Bip01 R Finger41',   'Bip01 Finger4.R', ),
SkeletonBone('Bip01 Finger42.R',  'Bip01 R Finger42',   'Bip01 Finger41.R', ),
SkeletonBone('Bip01 ForeTwistDriver.R',  'Bip01 R ForeTwistDriver',   'Bip01 UpperArm.R', ),
SkeletonBone('Bip01 Pauldron.L',  'Bip01 LPauldron',   'Bip01 Spine2', ),
SkeletonBone('Bip01 Pauldron.R',  'Bip01 RPauldron',   'Bip01 Spine2', ),
SkeletonBone('Bip01 Breast01.L',  'Bip01 L Breast01',   'Bip01 Spine2', ),
SkeletonBone('Bip01 Breast02.L',  'Bip01 L Breast02',   'Bip01 Breast01.L', ),
SkeletonBone('Bip01 Breast03.L',  'Bip01 L Breast03',   'Bip01 Breast02.L', ),
SkeletonBone('Bip01 Breast01.R',  'Bip01 R Breast01',   'Bip01 Spine2', ),
SkeletonBone('Bip01 Breast02.R',  'Bip01 R Breast02',   'Bip01 Breast01.R', ),
SkeletonBone('Bip01 Breast03.R',  'Bip01 R Breast03',   'Bip01 Breast02.R', ),
SkeletonBone('breast.L',  'breast.L',   'Bip01 Spine2', ),
SkeletonBone('breast.R',  'breast.R',   'Bip01 Spine2', ),
]

fnvExpressions = []

fnvParts = []

fnvDict = BoneDict(fnvBones, fnvExpressions, fnvParts)

skyrimBones = [
# PyNifly, Vanilla, Parent, NifTools
SkeletonBone('1H Axes on Back', '1H Axes on Back', 'Weapon Spine2', '1H Axes on Back'),
SkeletonBone('1H Swords on Back', '1H Swords on Back', 'Weapon Spine2', '1H Swords on Back'),
SkeletonBone('Aesthetic Bolt Quiver', 'Aesthetic Bolt Quiver', 'Weapon Pelvis', 'Aesthetic Bolt Quiver'),
SkeletonBone('AnimObjectA', 'AnimObjectA', 'NPC Root [Root]', 'AnimObjectA'),
SkeletonBone('AnimObjectB', 'AnimObjectB', 'NPC Root [Root]', 'AnimObjectB'),
SkeletonBone('AnimObject.L', 'AnimObjectL', 'CME L Hand [LHnd]', 'AnimObjectL'),
SkeletonBone('AnimObject.R', 'AnimObjectR', 'CME R Hand [RHnd]', 'AnimObjectR'),
SkeletonBone('Ankle Dagger Main', 'Ankle Dagger Main', 'Weapon R Calf', 'Ankle Dagger Main'),
SkeletonBone('Ankle Dagger Offhand', 'Ankle Dagger Offhand', 'Weapon L Calf', 'Ankle Dagger Offhand'),
SkeletonBone('BOLT', 'BOLT', 'MOV BOLT', 'BOLT'),
SkeletonBone('BOLTABQ', 'BOLTABQ', 'MOV BOLTABQ', 'BOLTABQ'),
SkeletonBone('BOLTChesko', 'BOLTChesko', 'MOV BOLTChesko', 'BOLTChesko'),
SkeletonBone('BOLTDefault', 'BOLTDefault', 'MOV BOLTDefault', 'BOLTDefault'),
SkeletonBone('BOLTLeftHipBolt', 'BOLTLeftHipBolt', 'MOV BOLTLeftHipBolt', 'BOLTLeftHipBolt'),
SkeletonBone('BOLTXP32', 'BOLTXP32', 'MOV BOLTXP32', 'BOLTXP32'),
SkeletonBone('BOLT_QUIVER', 'BOLT_QUIVER', 'MOV BOLT_QUIVER', 'BOLT_QUIVER'),
SkeletonBone('Back Hip Dagger', 'Back Hip Dagger', 'Weapon Pelvis', 'Back Hip Dagger'),
SkeletonBone('Belly', 'Belly', 'NPC Spine1 [Spn1]', 'Belly'),
SkeletonBone('Better Bow', 'Better Bow', 'Weapon Spine2', 'Better Bow'),
SkeletonBone('Bolt Quiver', 'Bolt Quiver', 'Weapon Pelvis', 'Bolt Quiver'),
SkeletonBone('Breast', 'Breast', 'CME Spine2 [Spn2]', 'Breast'),
SkeletonBone('Butt', 'Butt', 'CME Pelvis [Pelv]', 'Butt'),
SkeletonBone('CME BOLT', 'CME BOLT', 'Bolt Quiver', 'CME BOLT'),
SkeletonBone('CME BOLTABQ', 'CME BOLTABQ', 'Aesthetic Bolt Quiver', 'CME BOLTABQ'),
SkeletonBone('CME BOLTChesko', 'CME BOLTChesko', 'Chesko Quiver', 'CME BOLTChesko'),
SkeletonBone('CME BOLTDefault', 'CME BOLTDefault', 'Default Bow and Quiver', 'CME BOLTDefault'),
SkeletonBone('CME BOLTLeftHipBolt', 'CME BOLTLeftHipBolt', 'Left Hip Bolt Quiver', 'CME BOLTLeftHipBolt'),
SkeletonBone('CME BOLTXP32', 'CME BOLTXP32', 'Bolt Quiver', 'CME BOLTXP32'),
SkeletonBone('CME BOLT_QUIVER', 'CME BOLT_QUIVER', 'Aesthetic Bolt Quiver', 'CME BOLT_QUIVER'),
SkeletonBone('CME Body', 'CME Body [Body]', 'NPC COM [COM ]', 'CME Body [Body]'),
SkeletonBone('CME Camera3rd', 'CME Camera3rd [Cam3]', None, 'CME Camera3rd [Cam3]'),
SkeletonBone('CME Genitals01', 'CME Genitals01 [Gen01]', 'NPC Genitals01 [Gen01]', 'CME Genitals01 [Gen01]'),
SkeletonBone('CME Genitals02', 'CME Genitals02 [Gen02]', 'NPC Genitals02 [Gen02]', 'CME Genitals02 [Gen02]'),
SkeletonBone('CME Genitals03', 'CME Genitals03 [Gen03]', 'NPC Genitals03 [Gen03]', 'CME Genitals03 [Gen03]'),
SkeletonBone('CME Genitals04', 'CME Genitals04 [Gen04]', 'NPC Genitals04 [Gen04]', 'CME Genitals04 [Gen04]'),
SkeletonBone('CME Genitals05', 'CME Genitals05 [Gen05]', 'NPC Genitals05 [Gen05]', 'CME Genitals05 [Gen05]'),
SkeletonBone('CME GenitalsBase', 'CME GenitalsBase [GenBase]', 'NPC GenitalsBase [GenBase]', 'CME GenitalsBase [GenBase]'),
SkeletonBone('CME GenitalsScrotum', 'CME GenitalsScrotum [GenScrot]', 'NPC GenitalsScrotum [GenScrot]', 'CME GenitalsScrotum [GenScrot]'),
SkeletonBone('CME Breast.L', 'CME L Breast', 'NPC L Breast', 'CME L Breast'),
SkeletonBone('CME Calf.L', 'CME L Calf [LClf]', 'NPC L Calf [LClf]', 'CME L Calf [LClf]'),
SkeletonBone('CME Clavicle.L', 'CME L Clavicle [LClv]', 'NPC L Clavicle [LClv]', 'CME L Clavicle [LClv]'),
SkeletonBone('CME Finger00.L', 'CME L Finger00 [LF00]', 'NPC L Finger00 [LF00]', 'CME L Finger00 [LF00]'),
SkeletonBone('CME Finger01.L', 'CME L Finger01 [LF01]', 'NPC L Finger01 [LF01]', 'CME L Finger01 [LF01]'),
SkeletonBone('CME Finger10.L', 'CME L Finger10 [LF10]', 'NPC L Finger10 [LF10]', 'CME L Finger10 [LF10]'),
SkeletonBone('CME Finger11.L', 'CME L Finger11 [LF11]', 'NPC L Finger11 [LF11]', 'CME L Finger11 [LF11]'),
SkeletonBone('CME Finger20.L', 'CME L Finger20 [LF20]', 'NPC L Finger20 [LF20]', 'CME L Finger20 [LF20]'),
SkeletonBone('CME Finger21.L', 'CME L Finger21 [LF21]', 'NPC L Finger21 [LF21]', 'CME L Finger21 [LF21]'),
SkeletonBone('CME Finger30.L', 'CME L Finger30 [LF30]', 'NPC L Finger30 [LF30]', 'CME L Finger30 [LF30]'),
SkeletonBone('CME Finger31.L', 'CME L Finger31 [LF31]', 'NPC L Finger31 [LF31]', 'CME L Finger31 [LF31]'),
SkeletonBone('CME Finger40.L', 'CME L Finger40 [LF40]', 'NPC L Finger40 [LF40]', 'CME L Finger40 [LF40]'),
SkeletonBone('CME Finger41.L', 'CME L Finger41 [LF41]', 'NPC L Finger41 [LF41]', 'CME L Finger41 [LF41]'),
SkeletonBone('CME Foot.L', 'CME L Foot [Lft ]', 'NPC L Foot [Lft ]', 'CME L Foot [Lft ]'),
SkeletonBone('CME Forearm.L', 'CME L Forearm [LLar]', 'NPC L Forearm [LLar]', 'CME L Forearm [LLar]'),
SkeletonBone('CME Hand.L', 'CME L Hand [LHnd]', 'NPC L Hand [LHnd]', 'CME L Hand [LHnd]'),
SkeletonBone('CME Hip.L', 'CME L Hip', 'CME Pelvis [Pelv]', 'CME L Hip'),
SkeletonBone('CME Knee.L', 'CME L Knee [LKne]', 'CME L Calf [LClf]', 'CME L Knee [LKne]'),
SkeletonBone('CME PreBreast.L', 'CME L PreBreast', 'NPC L PreBreast', 'CME L PreBreast'),
SkeletonBone('CME PreBreastRoot.L', 'CME L PreBreastRoot', 'Breast', 'CME L PreBreastRoot'),
SkeletonBone('CME PreButt.L', 'CME L PreButt', 'NPC L PreButt', 'CME L PreButt'),
SkeletonBone('CME PreButt0.L', 'CME L PreButt0', 'NPC L PreButt0', 'CME L PreButt0'),
SkeletonBone('CME PreButtRoot.L', 'CME L PreButtRoot', 'Butt', 'CME L PreButtRoot'),
SkeletonBone('CME Shoulder.L', 'CME L Shoulder', 'CME Spine2 [Spn2]', 'CME L Shoulder'),
SkeletonBone('CME Thigh.L', 'CME L Thigh [LThg]', 'NPC L Thigh [LThg]', 'CME L Thigh [LThg]'),
SkeletonBone('CME Toe0.L', 'CME L Toe0 [LToe]', 'NPC L Toe0 [LToe]', 'CME L Toe0 [LToe]'),
SkeletonBone('CME UpperArm.L', 'CME L UpperArm [LUar]', 'NPC L UpperArm [LUar]', 'CME L UpperArm [LUar]'),
SkeletonBone('CME LBody', 'CME LBody [LBody]', 'CME Body [Body]', 'CME LBody [LBody]'),
SkeletonBone('CME Neck', 'CME Neck [Neck]', 'NPC Neck [Neck]', 'CME Neck [Neck]'),
SkeletonBone('CME Pelvis', 'CME Pelvis [Pelv]', 'NPC Pelvis [Pelv]', 'CME Pelvis [Pelv]'),
SkeletonBone('CME QUIVERChesko', 'CME QUIVERChesko', 'Chesko Quiver', 'CME QUIVERChesko'),
SkeletonBone('CME QUIVERDefault', 'CME QUIVERDefault', 'Default Bow and Quiver', 'CME QUIVERDefault'),
SkeletonBone('CME QUIVERLeftHipBolt', 'CME QUIVERLeftHipBolt', 'Left Hip Bolt Quiver', 'CME QUIVERLeftHipBolt'),
SkeletonBone('CME Breast.R', 'CME R Breast', 'NPC R Breast', 'CME R Breast'),
SkeletonBone('CME Calf.R', 'CME R Calf [RClf]', 'NPC R Calf [RClf]', 'CME R Calf [RClf]'),
SkeletonBone('CME Clavicle.R', 'CME R Clavicle [RClv]', 'NPC R Clavicle [RClv]', 'CME R Clavicle [RClv]'),
SkeletonBone('CME Finger00.R', 'CME R Finger00 [RF00]', 'NPC R Finger00 [RF00]', 'CME R Finger00 [RF00]'),
SkeletonBone('CME Finger01.R', 'CME R Finger01 [RF01]', 'NPC R Finger01 [RF01]', 'CME R Finger01 [RF01]'),
SkeletonBone('CME Finger10.R', 'CME R Finger10 [RF10]', 'NPC R Finger10 [RF10]', 'CME R Finger10 [RF10]'),
SkeletonBone('CME Finger11.R', 'CME R Finger11 [RF11]', 'NPC R Finger11 [RF11]', 'CME R Finger11 [RF11]'),
SkeletonBone('CME Finger20.R', 'CME R Finger20 [RF20]', 'NPC R Finger20 [RF20]', 'CME R Finger20 [RF20]'),
SkeletonBone('CME Finger21.R', 'CME R Finger21 [RF21]', 'NPC R Finger21 [RF21]', 'CME R Finger21 [RF21]'),
SkeletonBone('CME Finger30.R', 'CME R Finger30 [RF30]', 'NPC R Finger30 [RF30]', 'CME R Finger30 [RF30]'),
SkeletonBone('CME Finger31.R', 'CME R Finger31 [RF31]', 'NPC R Finger31 [RF31]', 'CME R Finger31 [RF31]'),
SkeletonBone('CME Finger40.R', 'CME R Finger40 [RF40]', 'NPC R Finger40 [RF40]', 'CME R Finger40 [RF40]'),
SkeletonBone('CME Finger41.R', 'CME R Finger41 [RF41]', 'NPC R Finger41 [RF41]', 'CME R Finger41 [RF41]'),
SkeletonBone('CME Foot.R', 'CME R Foot [Rft ]', 'NPC R Foot [Rft ]', 'CME R Foot [Rft ]'),
SkeletonBone('CME Forearm.R', 'CME R Forearm [RLar]', 'NPC R Forearm [RLar]', 'CME R Forearm [RLar]'),
SkeletonBone('CME Hand.R', 'CME R Hand [RHnd]', 'NPC R Hand [RHnd]', 'CME R Hand [RHnd]'),
SkeletonBone('CME Hip.R', 'CME R Hip', 'CME Pelvis [Pelv]', 'CME R Hip'),
SkeletonBone('CME Knee.R', 'CME R Knee [RKne]', 'CME R Calf [RClf]', 'CME R Knee [RKne]'),
SkeletonBone('CME PreBreast.R', 'CME R PreBreast', 'NPC R PreBreast', 'CME R PreBreast'),
SkeletonBone('CME PreBreastRoot.R', 'CME R PreBreastRoot', 'Breast', 'CME R PreBreastRoot'),
SkeletonBone('CME PreButt.R', 'CME R PreButt', 'NPC R PreButt', 'CME R PreButt'),
SkeletonBone('CME PreButt0.R', 'CME R PreButt0', 'NPC R PreButt0', 'CME R PreButt0'),
SkeletonBone('CME PreButtRoot.R', 'CME R PreButtRoot', 'Butt', 'CME R PreButtRoot'),
SkeletonBone('CME Shoulder.R', 'CME R Shoulder', 'CME Spine2 [Spn2]', 'CME R Shoulder'),
SkeletonBone('CME Thigh.R', 'CME R Thigh [RThg]', 'NPC R Thigh [RThg]', 'CME R Thigh [RThg]'),
SkeletonBone('CME Toe0.R', 'CME R Toe0 [RToe]', 'NPC R Toe0 [RToe]', 'CME R Toe0 [RToe]'),
SkeletonBone('CME UpperArm.R', 'CME R UpperArm [RUar]', 'NPC R UpperArm [RUar]', 'CME R UpperArm [RUar]'),
SkeletonBone('CME SchlongMagic', 'CME SchlongMagic', 'NPC Genitals02 [Gen02]', 'CME SchlongMagic'),
SkeletonBone('CME ShieldBackDefault', 'CME ShieldBackDefault', 'Default ShieldBack', 'CME ShieldBackDefault'),
SkeletonBone('CME Spine', 'CME Spine [Spn0]', 'NPC Spine [Spn0]', 'CME Spine [Spn0]'),
SkeletonBone('CME Spine1', 'CME Spine1 [Spn1]', 'NPC Spine1 [Spn1]', 'CME Spine1 [Spn1]'),
SkeletonBone('CME Spine2', 'CME Spine2 [Spn2]', 'NPC Spine2 [Spn2]', 'CME Spine2 [Spn2]'),
SkeletonBone('CME Tail Thigh.L', 'CME Tail L Thigh [LThg]', 'CME L Thigh [LThg]', 'CME Tail L Thigh [LThg]'),
SkeletonBone('CME Tail Pelvis', 'CME Tail Pelvis [Pelv]', 'Tails', 'CME Tail Pelvis [Pelv]'),
SkeletonBone('CME Tail Thigh.R', 'CME Tail R Thigh [RThg]', 'CME R Thigh [RThg]', 'CME Tail R Thigh [RThg]'),
SkeletonBone('CME Tail Spine', 'CME Tail Spine [Spn0]', 'CME Spine [Spn0]', 'CME Tail Spine [Spn0]'),
SkeletonBone('CME Tail Spine1', 'CME Tail Spine1 [Spn1]', 'NPC Spine1 [Spn1]', 'CME Tail Spine1 [Spn1]'),
SkeletonBone('CME TailBone01', 'CME TailBone01', 'TailBone01', 'CME TailBone01'),
SkeletonBone('CME TailBone02', 'CME TailBone02', 'TailBone02', 'CME TailBone02'),
SkeletonBone('CME TailBone03', 'CME TailBone03', 'TailBone03', 'CME TailBone03'),
SkeletonBone('CME TailBone04', 'CME TailBone04', 'TailBone04', 'CME TailBone04'),
SkeletonBone('CME UBody', 'CME UBody [UBody]', 'CME Body [Body]', 'CME UBody [UBody]'),
SkeletonBone('CME WeaponAxeDefault', 'CME WeaponAxeDefault', 'Default Axe', 'CME WeaponAxeDefault'),
SkeletonBone('CME WeaponAxeDefault.L', 'CME WeaponAxeLeftDefault', 'Default Axe', 'CME WeaponAxeLeftDefault'),
SkeletonBone('CME WeaponAxeOnBack.L', 'CME WeaponAxeLeftOnBack', '1H Axes on Back', 'CME WeaponAxeLeftOnBack'),
SkeletonBone('CME WeaponAxeReverse.L', 'CME WeaponAxeLeftReverse', 'Reverse Axe', 'CME WeaponAxeLeftReverse'),
SkeletonBone('CME WeaponAxeOnBack', 'CME WeaponAxeOnBack', '1H Axes on Back', 'CME WeaponAxeOnBack'),
SkeletonBone('CME WeaponAxeReverse', 'CME WeaponAxeReverse', 'Reverse Axe', 'CME WeaponAxeReverse'),
SkeletonBone('CME WeaponBackAxeMaceDefault', 'CME WeaponBackAxeMaceDefault', 'Default WeaponBackAxeMace', 'CME WeaponBackAxeMaceDefault'),
SkeletonBone('CME WeaponBackAxeMaceFSM', 'CME WeaponBackAxeMaceFSM', 'FSM WeaponBackAxeMace', 'CME WeaponBackAxeMaceFSM'),
SkeletonBone('CME WeaponBackAxeMaceSWP', 'CME WeaponBackAxeMaceSWP', 'SWP WeaponBackAxeMace', 'CME WeaponBackAxeMaceSWP'),
SkeletonBone('CME WeaponBackDefault', 'CME WeaponBackDefault', 'Default WeaponBack', 'CME WeaponBackDefault'),
SkeletonBone('CME WeaponBackFSM', 'CME WeaponBackFSM', 'FSM WeaponBack', 'CME WeaponBackFSM'),
SkeletonBone('CME WeaponBackSWP', 'CME WeaponBackSWP', 'SWP WeaponBack', 'CME WeaponBackSWP'),
SkeletonBone('CME WeaponBowBetter', 'CME WeaponBowBetter', 'Better Bow', 'CME WeaponBowBetter'),
SkeletonBone('CME WeaponBowChesko', 'CME WeaponBowChesko', 'Chesko Bow', 'CME WeaponBowChesko'),
SkeletonBone('CME WeaponBowDefault', 'CME WeaponBowDefault', 'Default Bow and Quiver', 'CME WeaponBowDefault'),
SkeletonBone('CME WeaponBowFSM', 'CME WeaponBowFSM', 'FSM Bow', 'CME WeaponBowFSM'),
SkeletonBone('CME WeaponCrossBowChesko', 'CME WeaponCrossBowChesko', 'Chesko Bow', 'CME WeaponCrossBowChesko'),
SkeletonBone('CME WeaponCrossBowDefault', 'CME WeaponCrossBowDefault', 'Default Bow and Quiver', 'CME WeaponCrossBowDefault'),
SkeletonBone('CME WeaponDaggerAnkle', 'CME WeaponDaggerAnkle', 'Ankle Dagger Main', 'CME WeaponDaggerAnkle'),
SkeletonBone('CME WeaponDaggerBackHip', 'CME WeaponDaggerBackHip', 'Back Hip Dagger', 'CME WeaponDaggerBackHip'),
SkeletonBone('CME WeaponDaggerDefault', 'CME WeaponDaggerDefault', 'Default Dagger', 'CME WeaponDaggerDefault'),
SkeletonBone('CME WeaponDaggerAnkle.L', 'CME WeaponDaggerLeftAnkle', 'Ankle Dagger Offhand', 'CME WeaponDaggerLeftAnkle'),
SkeletonBone('CME WeaponDaggerBackHip.L', 'CME WeaponDaggerLeftBackHip', 'Back Hip Dagger', 'CME WeaponDaggerLeftBackHip'),
SkeletonBone('CME WeaponDaggerDefault.L', 'CME WeaponDaggerLeftDefault', 'Default Dagger', 'CME WeaponDaggerLeftDefault'),
SkeletonBone('CME WeaponMaceDefault', 'CME WeaponMaceDefault', 'Default Mace', 'CME WeaponMaceDefault'),
SkeletonBone('CME WeaponMaceDefault.L', 'CME WeaponMaceLeftDefault', 'Default Mace', 'CME WeaponMaceLeftDefault'),
SkeletonBone('CME WeaponStaffDefault', 'CME WeaponStaffDefault', 'Default Staff', 'CME WeaponStaffDefault'),
SkeletonBone('CME WeaponStaffDefault.L', 'CME WeaponStaffLeftDefault', 'Default Staff', 'CME WeaponStaffLeftDefault'),
SkeletonBone('CME WeaponSwordDefault', 'CME WeaponSwordDefault', 'Default Sword', 'CME WeaponSwordDefault'),
SkeletonBone('CME WeaponSwordFSM', 'CME WeaponSwordFSM', 'FSM Sword', 'CME WeaponSwordFSM'),
SkeletonBone('CME WeaponSwordDefault.L', 'CME WeaponSwordLeftDefault', 'Default Sword', 'CME WeaponSwordLeftDefault'),
SkeletonBone('CME WeaponSwordFSM.L', 'CME WeaponSwordLeftFSM', 'FSM Sword', 'CME WeaponSwordLeftFSM'),
SkeletonBone('CME WeaponSwordHip.L', 'CME WeaponSwordLeftHip', 'Left Hip Swords', 'CME WeaponSwordLeftHip'),
SkeletonBone('CME WeaponSwordLeftHip.L', 'CME WeaponSwordLeftLeftHip', 'Left Hip Swords', 'CME WeaponSwordLeftLeftHip'),
SkeletonBone('CME WeaponSwordNMD.L', 'CME WeaponSwordLeftNMD', 'NMD Sword', 'CME WeaponSwordLeftNMD'),
SkeletonBone('CME WeaponSwordOnBack.L', 'CME WeaponSwordLeftOnBack', '1H Swords on Back', 'CME WeaponSwordLeftOnBack'),
SkeletonBone('CME WeaponSwordSWP.L', 'CME WeaponSwordLeftSWP', 'SWP Swords on Back', 'CME WeaponSwordLeftSWP'),
SkeletonBone('CME WeaponSwordNMD', 'CME WeaponSwordNMD', 'NMD Sword', 'CME WeaponSwordNMD'),
SkeletonBone('CME WeaponSwordOnBack', 'CME WeaponSwordOnBack', '1H Swords on Back', 'CME WeaponSwordOnBack'),
SkeletonBone('CME WeaponSwordSWP', 'CME WeaponSwordSWP', 'SWP Swords on Back', 'CME WeaponSwordSWP'),
SkeletonBone('Camera Control', 'Camera Control', 'NPC Root [Root]', 'Camera Control'),
SkeletonBone('Camera3rd', 'Camera3rd [Cam3]', 'CME Camera3rd [Cam3]', 'Camera3rd [Cam3]'),
SkeletonBone('CharacterBumper', 'CharacterBumper', None, 'CharacterBumper'),
SkeletonBone('Chesko Bow', 'Chesko Bow', 'Weapon Spine2', 'Chesko Bow'),
SkeletonBone('Chesko Quiver', 'Chesko Quiver', 'Weapon Spine1', 'Chesko Quiver'),
SkeletonBone('Default Axe', 'Default Axe', 'Weapon Pelvis', 'Default Axe'),
SkeletonBone('Default Bow and Quiver', 'Default Bow and Quiver', 'Weapon Spine2', 'Default Bow and Quiver'),
SkeletonBone('Default Dagger', 'Default Dagger', 'Weapon Pelvis', 'Default Dagger'),
SkeletonBone('Default Mace', 'Default Mace', 'Weapon Pelvis', 'Default Mace'),
SkeletonBone('Default ShieldBack', 'Default ShieldBack', 'Weapon Spine2', 'Default ShieldBack'),
SkeletonBone('Default Staff', 'Default Staff', 'Weapon Spine2', 'Default Staff'),
SkeletonBone('Default Sword', 'Default Sword', 'Weapon Pelvis', 'Default Sword'),
SkeletonBone('Default WeaponBack', 'Default WeaponBack', 'Weapon Spine2', 'Default WeaponBack'),
SkeletonBone('Default WeaponBackAxeMace', 'Default WeaponBackAxeMace', 'Weapon Spine2', 'Default WeaponBackAxeMace'),
SkeletonBone('FSM Bow', 'FSM Bow', 'Weapon Spine2', 'FSM Bow'),
SkeletonBone('FSM Sword', 'FSM Sword', 'Weapon Pelvis', 'FSM Sword'),
SkeletonBone('FSM WeaponBack', 'FSM WeaponBack', 'Weapon Pelvis', 'FSM WeaponBack'),
SkeletonBone('FSM WeaponBackAxeMace', 'FSM WeaponBackAxeMace', 'Weapon Pelvis', 'FSM WeaponBackAxeMace'),
SkeletonBone('Genitals', 'Genitals', 'CME Pelvis [Pelv]', 'Genitals'),
SkeletonBone('GenitalsLag01', 'GenitalsLag01', 'CME GenitalsBase [GenBase]', 'GenitalsLag01'),
SkeletonBone('GenitalsLag02', 'GenitalsLag02', 'CME Genitals01 [Gen01]', 'GenitalsLag02'),
SkeletonBone('GenitalsLag03', 'GenitalsLag03', 'CME Genitals02 [Gen02]', 'GenitalsLag03'),
SkeletonBone('GenitalsLag04', 'GenitalsLag04', 'CME Genitals03 [Gen03]', 'GenitalsLag04'),
SkeletonBone('GenitalsLag05', 'GenitalsLag05', 'CME Genitals04 [Gen04]', 'GenitalsLag05'),
SkeletonBone('GenitalsLag06', 'GenitalsLag06', 'CME Genitals05 [Gen05]', 'GenitalsLag06'),
SkeletonBone('GenitalsScrotumLag', 'GenitalsScrotumLag', 'CME GenitalsBase [GenBase]', 'GenitalsScrotumLag'),
SkeletonBone('HDT Belly', 'HDT Belly', 'Belly', 'HDT Belly'),
SkeletonBone('HDT QUIVER', 'HDT QUIVER', 'MOV QUIVERDefault', 'HDT QUIVER'),
SkeletonBone('HDT ShieldBack', 'HDT ShieldBack', 'MOV ShieldBackDefault', 'HDT ShieldBack'),
SkeletonBone('HDT Tail', 'HDT Tail', 'CME Tail Pelvis [Pelv]', 'HDT Tail'),
SkeletonBone('HDT TailBone01', 'HDT TailBone01', 'HDT Tail', 'HDT TailBone01'),
SkeletonBone('HDT TailBone01.1', 'HDT TailBone01.1', 'HDT TailBone01', 'HDT TailBone01.1'),
SkeletonBone('HDT TailBone01.2', 'HDT TailBone01.2', 'HDT TailBone01.1', 'HDT TailBone01.2'),
SkeletonBone('HDT TailBone01.3', 'HDT TailBone01.3', 'HDT TailBone01.2', 'HDT TailBone01.3'),
SkeletonBone('HDT TailBone02', 'HDT TailBone02', 'HDT TailBone01.3', 'HDT TailBone02'),
SkeletonBone('HDT TailBone02.1', 'HDT TailBone02.1', 'HDT TailBone02', 'HDT TailBone02.1'),
SkeletonBone('HDT TailBone02.2', 'HDT TailBone02.2', 'HDT TailBone02.1', 'HDT TailBone02.2'),
SkeletonBone('HDT TailBone02.3', 'HDT TailBone02.3', 'HDT TailBone02.2', 'HDT TailBone02.3'),
SkeletonBone('HDT TailBone03', 'HDT TailBone03', 'HDT TailBone02.3', 'HDT TailBone03'),
SkeletonBone('HDT TailBone03.1', 'HDT TailBone03.1', 'HDT TailBone03', 'HDT TailBone03.1'),
SkeletonBone('HDT TailBone03.2', 'HDT TailBone03.2', 'HDT TailBone03.1', 'HDT TailBone03.2'),
SkeletonBone('HDT TailBone03.3', 'HDT TailBone03.3', 'HDT TailBone03.2', 'HDT TailBone03.3'),
SkeletonBone('HDT TailBone04', 'HDT TailBone04', 'HDT TailBone03.3', 'HDT TailBone04'),
SkeletonBone('HDT TailBone04.1', 'HDT TailBone04.1', 'HDT TailBone04', 'HDT TailBone04.1'),
SkeletonBone('HDT TailBone04.2', 'HDT TailBone04.2', 'HDT TailBone04.1', 'HDT TailBone04.2'),
SkeletonBone('HDT TailBone04.3', 'HDT TailBone04.3', 'HDT TailBone04.2', 'HDT TailBone04.3'),
SkeletonBone('HDT TailBone05', 'HDT TailBone05', 'HDT TailBone04.3', 'HDT TailBone05'),
SkeletonBone('HDT TailBone05.1', 'HDT TailBone05.1', 'HDT TailBone05', 'HDT TailBone05.1'),
SkeletonBone('HDT TailBone05.2', 'HDT TailBone05.2', 'HDT TailBone05.1', 'HDT TailBone05.2'),
SkeletonBone('HDT TailBone05.3', 'HDT TailBone05.3', 'HDT TailBone05.2', 'HDT TailBone05.3'),
SkeletonBone('HDT TailBone06', 'HDT TailBone06', 'HDT TailBone05.3', 'HDT TailBone06'),
SkeletonBone('HDT WeaponAxe', 'HDT WeaponAxe', 'MOV WeaponAxeDefault', 'HDT WeaponAxe'),
SkeletonBone('HDT WeaponAxe.L', 'HDT WeaponAxeLeft', 'MOV WeaponAxeLeftDefault', 'HDT WeaponAxeLeft'),
SkeletonBone('HDT WeaponBack', 'HDT WeaponBack', 'MOV WeaponBackDefault', 'HDT WeaponBack'),
SkeletonBone('HDT WeaponBow', 'HDT WeaponBow', 'MOV WeaponBowDefault', 'HDT WeaponBow'),
SkeletonBone('HDT WeaponDagger', 'HDT WeaponDagger', 'MOV WeaponDaggerDefault', 'HDT WeaponDagger'),
SkeletonBone('HDT WeaponDagger.L', 'HDT WeaponDaggerLeft', 'MOV WeaponDaggerLeftDefault', 'HDT WeaponDaggerLeft'),
SkeletonBone('HDT WeaponMace', 'HDT WeaponMace', 'MOV WeaponMaceDefault', 'HDT WeaponMace'),
SkeletonBone('HDT WeaponMace.L', 'HDT WeaponMaceLeft', 'MOV WeaponMaceLeftDefault', 'HDT WeaponMaceLeft'),
SkeletonBone('HDT WeaponStaff', 'HDT WeaponStaff', 'MOV WeaponStaffDefault', 'HDT WeaponStaff'),
SkeletonBone('HDT WeaponStaff.L', 'HDT WeaponStaffLeft', 'MOV WeaponStaffLeftDefault', 'HDT WeaponStaffLeft'),
SkeletonBone('HDT WeaponSword', 'HDT WeaponSword', 'MOV WeaponSwordDefault', 'HDT WeaponSword'),
SkeletonBone('HDT WeaponSword.L', 'HDT WeaponSwordLeft', 'MOV WeaponSwordLeftDefault', 'HDT WeaponSwordLeft'),
SkeletonBone('HorseSpine2', 'HorseSpine2', 'NPC COM [COM ]', 'HorseSpine2'),
SkeletonBone('Left Hip Bolt Quiver', 'Left Hip Bolt Quiver', 'Weapon Pelvis', 'Left Hip Bolt Quiver'),
SkeletonBone('Left Hip Swords', 'Left Hip Swords', 'Weapon Pelvis', 'Left Hip Swords'),
SkeletonBone('Wing1.L', 'LeftWing1', 'VampireLord Wings', 'LeftWing1'),
SkeletonBone('Wing2.L', 'LeftWing2', 'LeftWing1', 'LeftWing2'),
SkeletonBone('Wing3.L', 'LeftWing3', 'LeftWing2', 'LeftWing3'),
SkeletonBone('Wing4.L', 'LeftWing4', 'LeftWing3', 'LeftWing4'),
SkeletonBone('Wing5.L', 'LeftWing5', 'LeftWing4', 'LeftWing5'),
SkeletonBone('MOV BOLT', 'MOV BOLT', 'CME BOLT', 'MOV BOLT'),
SkeletonBone('MOV BOLTABQ', 'MOV BOLTABQ', 'CME BOLTABQ', 'MOV BOLTABQ'),
SkeletonBone('MOV BOLTChesko', 'MOV BOLTChesko', 'CME BOLTChesko', 'MOV BOLTChesko'),
SkeletonBone('MOV BOLTDefault', 'MOV BOLTDefault', 'CME BOLTDefault', 'MOV BOLTDefault'),
SkeletonBone('MOV BOLTLeftHipBolt', 'MOV BOLTLeftHipBolt', 'CME BOLTLeftHipBolt', 'MOV BOLTLeftHipBolt'),
SkeletonBone('MOV BOLTXP32', 'MOV BOLTXP32', 'CME BOLTXP32', 'MOV BOLTXP32'),
SkeletonBone('MOV BOLT_QUIVER', 'MOV BOLT_QUIVER', 'CME BOLT_QUIVER', 'MOV BOLT_QUIVER'),
SkeletonBone('MOV QUIVERChesko', 'MOV QUIVERChesko', 'CME QUIVERChesko', 'MOV QUIVERChesko'),
SkeletonBone('MOV QUIVERDefault', 'MOV QUIVERDefault', 'CME QUIVERDefault', 'MOV QUIVERDefault'),
SkeletonBone('MOV QUIVERLeftHipBolt', 'MOV QUIVERLeftHipBolt', 'CME QUIVERLeftHipBolt', 'MOV QUIVERLeftHipBolt'),
SkeletonBone('MOV ShieldBackDefault', 'MOV ShieldBackDefault', 'CME ShieldBackDefault', 'MOV ShieldBackDefault'),
SkeletonBone('MOV WeaponAxeDefault', 'MOV WeaponAxeDefault', 'CME WeaponAxeDefault', 'MOV WeaponAxeDefault'),
SkeletonBone('MOV WeaponAxeDefault.L', 'MOV WeaponAxeLeftDefault', 'CME WeaponAxeLeftDefault', 'MOV WeaponAxeLeftDefault'),
SkeletonBone('MOV WeaponAxeOnBack.L', 'MOV WeaponAxeLeftOnBack', 'CME WeaponAxeLeftOnBack', 'MOV WeaponAxeLeftOnBack'),
SkeletonBone('MOV WeaponAxeReverse.L', 'MOV WeaponAxeLeftReverse', 'CME WeaponAxeLeftReverse', 'MOV WeaponAxeLeftReverse'),
SkeletonBone('MOV WeaponAxeOnBack', 'MOV WeaponAxeOnBack', 'CME WeaponAxeOnBack', 'MOV WeaponAxeOnBack'),
SkeletonBone('MOV WeaponAxeReverse', 'MOV WeaponAxeReverse', 'CME WeaponAxeReverse', 'MOV WeaponAxeReverse'),
SkeletonBone('MOV WeaponBackAxeMaceDefault', 'MOV WeaponBackAxeMaceDefault', 'CME WeaponBackAxeMaceDefault', 'MOV WeaponBackAxeMaceDefault'),
SkeletonBone('MOV WeaponBackAxeMaceFSM', 'MOV WeaponBackAxeMaceFSM', 'CME WeaponBackAxeMaceFSM', 'MOV WeaponBackAxeMaceFSM'),
SkeletonBone('MOV WeaponBackAxeMaceSWP', 'MOV WeaponBackAxeMaceSWP', 'CME WeaponBackAxeMaceSWP', 'MOV WeaponBackAxeMaceSWP'),
SkeletonBone('MOV WeaponBackDefault', 'MOV WeaponBackDefault', 'CME WeaponBackDefault', 'MOV WeaponBackDefault'),
SkeletonBone('MOV WeaponBackFSM', 'MOV WeaponBackFSM', 'CME WeaponBackFSM', 'MOV WeaponBackFSM'),
SkeletonBone('MOV WeaponBackSWP', 'MOV WeaponBackSWP', 'CME WeaponBackSWP', 'MOV WeaponBackSWP'),
SkeletonBone('MOV WeaponBowBetter', 'MOV WeaponBowBetter', 'CME WeaponBowBetter', 'MOV WeaponBowBetter'),
SkeletonBone('MOV WeaponBowChesko', 'MOV WeaponBowChesko', 'CME WeaponBowChesko', 'MOV WeaponBowChesko'),
SkeletonBone('MOV WeaponBowDefault', 'MOV WeaponBowDefault', 'CME WeaponBowDefault', 'MOV WeaponBowDefault'),
SkeletonBone('MOV WeaponBowFSM', 'MOV WeaponBowFSM', 'CME WeaponBowFSM', 'MOV WeaponBowFSM'),
SkeletonBone('MOV WeaponCrossBowChesko', 'MOV WeaponCrossBowChesko', 'CME WeaponCrossBowChesko', 'MOV WeaponCrossBowChesko'),
SkeletonBone('MOV WeaponCrossBowDefault', 'MOV WeaponCrossBowDefault', 'CME WeaponCrossBowDefault', 'MOV WeaponCrossBowDefault'),
SkeletonBone('MOV WeaponDaggerAnkle', 'MOV WeaponDaggerAnkle', 'CME WeaponDaggerAnkle', 'MOV WeaponDaggerAnkle'),
SkeletonBone('MOV WeaponDaggerBackHip', 'MOV WeaponDaggerBackHip', 'CME WeaponDaggerBackHip', 'MOV WeaponDaggerBackHip'),
SkeletonBone('MOV WeaponDaggerDefault', 'MOV WeaponDaggerDefault', 'CME WeaponDaggerDefault', 'MOV WeaponDaggerDefault'),
SkeletonBone('MOV WeaponDaggerAnkle.L', 'MOV WeaponDaggerLeftAnkle', 'CME WeaponDaggerLeftAnkle', 'MOV WeaponDaggerLeftAnkle'),
SkeletonBone('MOV WeaponDaggerBackHip.L', 'MOV WeaponDaggerLeftBackHip', 'CME WeaponDaggerLeftBackHip', 'MOV WeaponDaggerLeftBackHip'),
SkeletonBone('MOV WeaponDaggerDefault.L', 'MOV WeaponDaggerLeftDefault', 'CME WeaponDaggerLeftDefault', 'MOV WeaponDaggerLeftDefault'),
SkeletonBone('MOV WeaponMaceDefault', 'MOV WeaponMaceDefault', 'CME WeaponMaceDefault', 'MOV WeaponMaceDefault'),
SkeletonBone('MOV WeaponMaceDefault.L', 'MOV WeaponMaceLeftDefault', 'CME WeaponMaceLeftDefault', 'MOV WeaponMaceLeftDefault'),
SkeletonBone('MOV WeaponStaffDefault', 'MOV WeaponStaffDefault', 'CME WeaponStaffDefault', 'MOV WeaponStaffDefault'),
SkeletonBone('MOV WeaponStaffDefault.L', 'MOV WeaponStaffLeftDefault', 'CME WeaponStaffLeftDefault', 'MOV WeaponStaffLeftDefault'),
SkeletonBone('MOV WeaponSwordDefault', 'MOV WeaponSwordDefault', 'CME WeaponSwordDefault', 'MOV WeaponSwordDefault'),
SkeletonBone('MOV WeaponSwordFSM', 'MOV WeaponSwordFSM', 'CME WeaponSwordFSM', 'MOV WeaponSwordFSM'),
SkeletonBone('MOV WeaponSwordDefault.L', 'MOV WeaponSwordLeftDefault', 'CME WeaponSwordLeftDefault', 'MOV WeaponSwordLeftDefault'),
SkeletonBone('MOV WeaponSwordFSM.L', 'MOV WeaponSwordLeftFSM', 'CME WeaponSwordLeftFSM', 'MOV WeaponSwordLeftFSM'),
SkeletonBone('MOV WeaponSwordHip.L', 'MOV WeaponSwordLeftHip', 'CME WeaponSwordLeftHip', 'MOV WeaponSwordLeftHip'),
SkeletonBone('MOV WeaponSwordLeftHip.L', 'MOV WeaponSwordLeftLeftHip', 'CME WeaponSwordLeftLeftHip', 'MOV WeaponSwordLeftLeftHip'),
SkeletonBone('MOV WeaponSwordNMD.L', 'MOV WeaponSwordLeftNMD', 'CME WeaponSwordLeftNMD', 'MOV WeaponSwordLeftNMD'),
SkeletonBone('MOV WeaponSwordOnBack.L', 'MOV WeaponSwordLeftOnBack', 'CME WeaponSwordLeftOnBack', 'MOV WeaponSwordLeftOnBack'),
SkeletonBone('MOV WeaponSwordSWP.L', 'MOV WeaponSwordLeftSWP', 'CME WeaponSwordLeftSWP', 'MOV WeaponSwordLeftSWP'),
SkeletonBone('MOV WeaponSwordNMD', 'MOV WeaponSwordNMD', 'CME WeaponSwordNMD', 'MOV WeaponSwordNMD'),
SkeletonBone('MOV WeaponSwordOnBack', 'MOV WeaponSwordOnBack', 'CME WeaponSwordOnBack', 'MOV WeaponSwordOnBack'),
SkeletonBone('MOV WeaponSwordSWP', 'MOV WeaponSwordSWP', 'CME WeaponSwordSWP', 'MOV WeaponSwordSWP'),
SkeletonBone('MagicEffectsNode', 'MagicEffectsNode', 'NPC Spine [Spn0]', 'MagicEffectsNode'),
SkeletonBone('NMD Sword', 'NMD Sword', 'Weapon Pelvis', 'NMD Sword'),
SkeletonBone('NPC', 'NPC', None, 'NPC'),
SkeletonBone('NPC Belly', 'NPC Belly', 'HDT Belly', 'NPC Belly'),
SkeletonBone('NPC COM', 'NPC COM [COM ]', 'NPC Root [Root]', 'NPC COM [COM ]'),
SkeletonBone('NPC Genitals01', 'NPC Genitals01 [Gen01]', 'GenitalsLag01', 'NPC Genitals01 [Gen01]'),
SkeletonBone('NPC Genitals02', 'NPC Genitals02 [Gen02]', 'GenitalsLag02', 'NPC Genitals02 [Gen02]'),
SkeletonBone('NPC Genitals03', 'NPC Genitals03 [Gen03]', 'GenitalsLag03', 'NPC Genitals03 [Gen03]'),
SkeletonBone('NPC Genitals04', 'NPC Genitals04 [Gen04]', 'GenitalsLag04', 'NPC Genitals04 [Gen04]'),
SkeletonBone('NPC Genitals05', 'NPC Genitals05 [Gen05]', 'GenitalsLag05', 'NPC Genitals05 [Gen05]'),
SkeletonBone('NPC Genitals06', 'NPC Genitals06 [Gen06]', 'GenitalsLag06', 'NPC Genitals06 [Gen06]'),
SkeletonBone('NPC GenitalsBase', 'NPC GenitalsBase [GenBase]', 'Schlong', 'NPC GenitalsBase [GenBase]'),
SkeletonBone('NPC GenitalsScrotum', 'NPC GenitalsScrotum [GenScrot]', 'GenitalsScrotumLag', 'NPC GenitalsScrotum [GenScrot]'),
SkeletonBone('NPC Head MagicNode', 'NPC Head MagicNode [Hmag]', 'NPC Head [Head]', 'NPC Head MagicNode [Hmag]'),
SkeletonBone('NPC Head', 'NPC Head [Head]', 'CME Neck [Neck]', 'NPC Head [Head]'),
SkeletonBone('NPC Breast.L', 'NPC L Breast', 'CME L PreBreast', 'NPC L Breast'),
SkeletonBone('NPC Breast01.L', 'NPC L Breast01', 'CME L Breast', 'NPC L Breast01'),
SkeletonBone('NPC Butt.L', 'NPC L Butt', 'CME L PreButt', 'NPC L Butt'),
SkeletonBone('NPC Calf.L', 'NPC L Calf [LClf]', 'CME L Thigh [LThg]', 'NPC Calf [Clf].L'),
SkeletonBone('NPC Clavicle.L', 'NPC L Clavicle [LClv]', 'CME L Shoulder', 'NPC Clavicle [Clv].L'),
SkeletonBone('NPC Finger00.L', 'NPC L Finger00 [LF00]', 'CME L Hand [LHnd]', 'NPC Finger00 [F00].L'),
SkeletonBone('NPC Finger01.L', 'NPC L Finger01 [LF01]', 'CME L Finger00 [LF00]', 'NPC Finger01 [F01].L'),
SkeletonBone('NPC Finger02.L', 'NPC L Finger02 [LF02]', 'CME L Finger01 [LF01]', 'NPC Finger02 [F02].L'),
SkeletonBone('NPC Finger10.L', 'NPC L Finger10 [LF10]', 'CME L Hand [LHnd]', 'NPC Finger10 [F10].L'),
SkeletonBone('NPC Finger11.L', 'NPC L Finger11 [LF11]', 'CME L Finger10 [LF10]', 'NPC Finger11 [F11].L'),
SkeletonBone('NPC Finger12.L', 'NPC L Finger12 [LF12]', 'CME L Finger11 [LF11]', 'NPC Finger12 [F12].L'),
SkeletonBone('NPC Finger20.L', 'NPC L Finger20 [LF20]', 'CME L Hand [LHnd]', 'NPC Finger20 [F20].L'),
SkeletonBone('NPC Finger21.L', 'NPC L Finger21 [LF21]', 'CME L Finger20 [LF20]', 'NPC Finger21 [F21].L'),
SkeletonBone('NPC Finger22.L', 'NPC L Finger22 [LF22]', 'CME L Finger21 [LF21]', 'NPC Finger22 [F22].L'),
SkeletonBone('NPC Finger30.L', 'NPC L Finger30 [LF30]', 'CME L Hand [LHnd]', 'NPC Finger30 [F30].L'),
SkeletonBone('NPC Finger31.L', 'NPC L Finger31 [LF31]', 'CME L Finger30 [LF30]', 'NPC Finger31 [F31].L'),
SkeletonBone('NPC Finger32.L', 'NPC L Finger32 [LF32]', 'CME L Finger31 [LF31]', 'NPC Finger32 [F32].L'),
SkeletonBone('NPC Finger40.L', 'NPC L Finger40 [LF40]', 'CME L Hand [LHnd]', 'NPC Finger40 [F40].L'),
SkeletonBone('NPC Finger41.L', 'NPC L Finger41 [LF41]', 'CME L Finger40 [LF40]', 'NPC Finger41 [F41].L'),
SkeletonBone('NPC Finger42.L', 'NPC L Finger42 [LF42]', 'CME L Finger41 [LF41]', 'NPC Finger42 [F42].L'),
SkeletonBone('NPC Foot.L', 'NPC L Foot [Lft ]', 'CME L Knee [LKne]', 'NPC Foot [ft ].L'),
SkeletonBone('NPC Forearm.L', 'NPC L Forearm [LLar]', 'CME L UpperArm [LUar]', 'NPC Forearm [Lar].L'),
SkeletonBone('NPC ForearmTwist1.L', 'NPC L ForearmTwist1 [LLt1]', 'CME L Forearm [LLar]', 'NPC ForearmTwist1 [Lt1].L'),
SkeletonBone('NPC ForearmTwist2.L', 'NPC L ForearmTwist2 [LLt2]', 'CME L Forearm [LLar]', 'NPC ForearmTwist2 [Lt2].L'),
SkeletonBone('NPC FrontThigh.L', 'NPC L FrontThigh', 'NPC L PreFrontThigh', 'NPC L FrontThigh'),
SkeletonBone('NPC GenitalsScrotum.L', 'NPC L GenitalsScrotum [LGenScrot]', 'CME GenitalsScrotum [GenScrot]', 'NPC L GenitalsScrotum [LGenScrot]'),
SkeletonBone('NPC Hand.L', 'NPC L Hand [LHnd]', 'CME L Forearm [LLar]', 'NPC Hand [Hnd].L'),
SkeletonBone('NPC Joint 1.L', 'NPC L Joint 1 [Lft ]', 'CME L Toe0 [LToe]', 'NPC L Joint 1 [Lft ]'),
SkeletonBone('NPC Joint 2.L', 'NPC L Joint 2 [Lft ]', 'CME L Toe0 [LToe]', 'NPC L Joint 2 [Lft ]'),
SkeletonBone('NPC Joint 3.L', 'NPC L Joint 3 [Lft ]', 'CME L Toe0 [LToe]', 'NPC L Joint 3 [Lft ]'),
SkeletonBone('NPC Joint 4.L', 'NPC L Joint 4 [Lft ]', 'CME L Toe0 [LToe]', 'NPC L Joint 4 [Lft ]'),
SkeletonBone('NPC Joint 5.L', 'NPC L Joint 5 [Lft ]', 'CME L Toe0 [LToe]', 'NPC L Joint 5 [Lft ]'),
SkeletonBone('NPC MagicNode.L', 'NPC L MagicNode [LMag]', 'CME L Hand [LHnd]', 'NPC MagicNode [Mag].L'),
SkeletonBone('NPC Pauldron.L', 'NPC L Pauldron', 'CME L Clavicle [LClv]', 'NPC L Pauldron'),
SkeletonBone('NPC PreBreast.L', 'NPC L PreBreast', 'CME L PreBreastRoot', 'NPC L PreBreast'),
SkeletonBone('NPC PreButt.L', 'NPC L PreButt', 'CME L PreButt0', 'NPC L PreButt'),
SkeletonBone('NPC PreButt0.L', 'NPC L PreButt0', 'CME L PreButtRoot', 'NPC L PreButt0'),
SkeletonBone('NPC PreFrontThigh.L', 'NPC L PreFrontThigh', 'CME L Thigh [LThg]', 'NPC L PreFrontThigh'),
SkeletonBone('NPC PreRearCalf.L', 'NPC L PreRearCalf', 'CME L Calf [LClf]', 'NPC L PreRearCalf'),
SkeletonBone('NPC PreRearThigh.L', 'NPC L PreRearThigh', 'CME L Thigh [LThg]', 'NPC L PreRearThigh'),
SkeletonBone('NPC RearCalf.L', 'NPC L RearCalf [LrClf]', 'NPC L PreRearCalf', 'NPC L RearCalf [LrClf]'),
SkeletonBone('NPC RearThigh.L', 'NPC L RearThigh', 'NPC L PreRearThigh', 'NPC L RearThigh'),
SkeletonBone('NPC ScaleBreast.L', 'NPC L ScaleBreast', 'CME L PreBreast', 'NPC L ScaleBreast'),
SkeletonBone('NPC ScaleButt.L', 'NPC L ScaleButt', 'CME L PreButt', 'NPC L ScaleButt'),
SkeletonBone('NPC Thigh.L', 'NPC L Thigh [LThg]', 'CME L Hip', 'NPC Thigh [Thg].L'),
SkeletonBone('NPC Toe 1.L', 'NPC L Toe 1 [Lft ]', 'NPC L Joint 1 [Lft ]', 'NPC L Toe 1 [Lft ]'),
SkeletonBone('NPC Toe 2.L', 'NPC L Toe 2 [Lft ]', 'NPC L Joint 2 [Lft ]', 'NPC L Toe 2 [Lft ]'),
SkeletonBone('NPC Toe 3.L', 'NPC L Toe 3 [Lft ]', 'NPC L Joint 3 [Lft ]', 'NPC L Toe 3 [Lft ]'),
SkeletonBone('NPC Toe 4.L', 'NPC L Toe 4 [Lft ]', 'NPC L Joint 4 [Lft ]', 'NPC L Toe 4 [Lft ]'),
SkeletonBone('NPC Toe 5.L', 'NPC L Toe 5 [Lft ]', 'NPC L Joint 5 [Lft ]', 'NPC L Toe 5 [Lft ]'),
SkeletonBone('NPC Toe0.L', 'NPC L Toe0 [LToe]', 'CME L Foot [Lft ]', 'NPC Toe0 [Toe].L'),
SkeletonBone('NPC UpperArm.L', 'NPC L UpperArm [LUar]', 'CME L Clavicle [LClv]', 'NPC UpperArm [Uar].L'),
SkeletonBone('NPC UpperarmTwist1.L', 'NPC L UpperarmTwist1 [LUt1]', 'CME L UpperArm [LUar]', 'NPC UpperarmTwist1 [Ut1].L'),
SkeletonBone('NPC UpperarmTwist2.L', 'NPC L UpperarmTwist2 [LUt2]', 'NPC L UpperarmTwist1 [LUt1]', 'NPC UpperarmTwist2 [Ut2].L'),
SkeletonBone('NPC Neck', 'NPC Neck [Neck]', 'CME Spine2 [Spn2]', 'NPC Neck [Neck]'),
SkeletonBone('NPC Pelvis', 'NPC Pelvis [Pelv]', 'CME LBody [LBody]', 'NPC Pelvis [Pelv]'),
SkeletonBone('NPC Breast.R', 'NPC R Breast', 'CME R PreBreast', 'NPC R Breast'),
SkeletonBone('NPC Breast01.R', 'NPC R Breast01', 'CME R Breast', 'NPC R Breast01'),
SkeletonBone('NPC Butt.R', 'NPC R Butt', 'CME R PreButt', 'NPC R Butt'),
SkeletonBone('NPC Calf.R', 'NPC R Calf [RClf]', 'CME R Thigh [RThg]', 'NPC Calf [Clf].R'),
SkeletonBone('NPC Clavicle.R', 'NPC R Clavicle [RClv]', 'CME R Shoulder', 'NPC Clavicle [Clv].R'),
SkeletonBone('NPC Finger00.R', 'NPC R Finger00 [RF00]', 'CME R Hand [RHnd]', 'NPC Finger00 [F00].R'),
SkeletonBone('NPC Finger01.R', 'NPC R Finger01 [RF01]', 'CME R Finger00 [RF00]', 'NPC Finger01 [F01].R'),
SkeletonBone('NPC Finger02.R', 'NPC R Finger02 [RF02]', 'CME R Finger01 [RF01]', 'NPC Finger02 [F02].R'),
SkeletonBone('NPC Finger10.R', 'NPC R Finger10 [RF10]', 'CME R Hand [RHnd]', 'NPC Finger10 [F10].R'),
SkeletonBone('NPC Finger11.R', 'NPC R Finger11 [RF11]', 'CME R Finger10 [RF10]', 'NPC Finger11 [F11].R'),
SkeletonBone('NPC Finger12.R', 'NPC R Finger12 [RF12]', 'CME R Finger11 [RF11]', 'NPC Finger12 [F12].R'),
SkeletonBone('NPC Finger20.R', 'NPC R Finger20 [RF20]', 'CME R Hand [RHnd]', 'NPC Finger20 [F20].R'),
SkeletonBone('NPC Finger21.R', 'NPC R Finger21 [RF21]', 'CME R Finger20 [RF20]', 'NPC Finger21 [F21].R'),
SkeletonBone('NPC Finger22.R', 'NPC R Finger22 [RF22]', 'CME R Finger21 [RF21]', 'NPC Finger22 [F22].R'),
SkeletonBone('NPC Finger30.R', 'NPC R Finger30 [RF30]', 'CME R Hand [RHnd]', 'NPC Finger30 [F30].R'),
SkeletonBone('NPC Finger31.R', 'NPC R Finger31 [RF31]', 'CME R Finger30 [RF30]', 'NPC Finger31 [F31].R'),
SkeletonBone('NPC Finger32.R', 'NPC R Finger32 [RF32]', 'CME R Finger31 [RF31]', 'NPC Finger32 [F32].R'),
SkeletonBone('NPC Finger40.R', 'NPC R Finger40 [RF40]', 'CME R Hand [RHnd]', 'NPC Finger40 [F40].R'),
SkeletonBone('NPC Finger41.R', 'NPC R Finger41 [RF41]', 'CME R Finger40 [RF40]', 'NPC Finger41 [F41].R'),
SkeletonBone('NPC Finger42.R', 'NPC R Finger42 [RF42]', 'CME R Finger41 [RF41]', 'NPC Finger42 [F42].R'),
SkeletonBone('NPC Foot.R', 'NPC R Foot [Rft ]', 'CME R Knee [RKne]', 'NPC Foot [ft ].R'),
SkeletonBone('NPC Forearm.R', 'NPC R Forearm [RLar]', 'CME R UpperArm [RUar]', 'NPC Forearm [Lar].R'),
SkeletonBone('NPC ForearmTwist1.R', 'NPC R ForearmTwist1 [RLt1]', 'CME R Forearm [RLar]', 'NPC ForearmTwist1 [Lt1].R'),
SkeletonBone('NPC ForearmTwist2.R', 'NPC R ForearmTwist2 [RLt2]', 'CME R Forearm [RLar]', 'NPC ForearmTwist2 [Lt2].R'),
SkeletonBone('NPC FrontThigh.R', 'NPC R FrontThigh', 'NPC R PreFrontThigh', 'NPC R FrontThigh'),
SkeletonBone('NPC GenitalsScrotum.R', 'NPC R GenitalsScrotum [RGenScrot]', 'CME GenitalsScrotum [GenScrot]', 'NPC R GenitalsScrotum [RGenScrot]'),
SkeletonBone('NPC Hand.R', 'NPC R Hand [RHnd]', 'CME R Forearm [RLar]', 'NPC Hand [Hnd].R'),
SkeletonBone('NPC Joint 1.R', 'NPC R Joint 1 [Rft ]', 'CME R Toe0 [RToe]', 'NPC R Joint 1 [Rft ]'),
SkeletonBone('NPC Joint 2.R', 'NPC R Joint 2 [Rft ]', 'CME R Toe0 [RToe]', 'NPC R Joint 2 [Rft ]'),
SkeletonBone('NPC Joint 3.R', 'NPC R Joint 3 [Rft ]', 'CME R Toe0 [RToe]', 'NPC R Joint 3 [Rft ]'),
SkeletonBone('NPC Joint 4.R', 'NPC R Joint 4 [Rft ]', 'CME R Toe0 [RToe]', 'NPC R Joint 4 [Rft ]'),
SkeletonBone('NPC Joint 5.R', 'NPC R Joint 5 [Rft ]', 'CME R Toe0 [RToe]', 'NPC R Joint 5 [Rft ]'),
SkeletonBone('NPC MagicNode.R', 'NPC R MagicNode [RMag]', 'CME R Hand [RHnd]', 'NPC MagicNode [Mag].R'),
SkeletonBone('NPC Pauldron.R', 'NPC R Pauldron', 'CME R Clavicle [RClv]', 'NPC R Pauldron'),
SkeletonBone('NPC PreBreast.R', 'NPC R PreBreast', 'CME R PreBreastRoot', 'NPC R PreBreast'),
SkeletonBone('NPC PreButt.R', 'NPC R PreButt', 'CME R PreButt0', 'NPC R PreButt'),
SkeletonBone('NPC PreButt0.R', 'NPC R PreButt0', 'CME R PreButtRoot', 'NPC R PreButt0'),
SkeletonBone('NPC PreFrontThigh.R', 'NPC R PreFrontThigh', 'CME R Thigh [RThg]', 'NPC R PreFrontThigh'),
SkeletonBone('NPC PreRearCalf.R', 'NPC R PreRearCalf', 'CME R Calf [RClf]', 'NPC R PreRearCalf'),
SkeletonBone('NPC PreRearThigh.R', 'NPC R PreRearThigh', 'CME R Thigh [RThg]', 'NPC R PreRearThigh'),
SkeletonBone('NPC RearCalf.R', 'NPC R RearCalf [RrClf]', 'NPC R PreRearCalf', 'NPC R RearCalf [RrClf]'),
SkeletonBone('NPC RearThigh.R', 'NPC R RearThigh', 'NPC R PreRearThigh', 'NPC R RearThigh'),
SkeletonBone('NPC ScaleBreast.R', 'NPC R ScaleBreast', 'CME R PreBreast', 'NPC R ScaleBreast'),
SkeletonBone('NPC ScaleButt.R', 'NPC R ScaleButt', 'CME R PreButt', 'NPC R ScaleButt'),
SkeletonBone('NPC Thigh.R', 'NPC R Thigh [RThg]', 'CME R Hip', 'NPC Thigh [Thg].R'),
SkeletonBone('NPC Toe 1.R', 'NPC R Toe 1 [Rft ]', 'NPC R Joint 1 [Rft ]', 'NPC R Toe 1 [Rft ]'),
SkeletonBone('NPC Toe 2.R', 'NPC R Toe 2 [Rft ]', 'NPC R Joint 2 [Rft ]', 'NPC R Toe 2 [Rft ]'),
SkeletonBone('NPC Toe 3.R', 'NPC R Toe 3 [Rft ]', 'NPC R Joint 3 [Rft ]', 'NPC R Toe 3 [Rft ]'),
SkeletonBone('NPC Toe 4.R', 'NPC R Toe 4 [Rft ]', 'NPC R Joint 4 [Rft ]', 'NPC R Toe 4 [Rft ]'),
SkeletonBone('NPC Toe 5.R', 'NPC R Toe 5 [Rft ]', 'NPC R Joint 5 [Rft ]', 'NPC R Toe 5 [Rft ]'),
SkeletonBone('NPC Toe0.R', 'NPC R Toe0 [RToe]', 'CME R Foot [Rft ]', 'NPC Toe0 [Toe].R'),
SkeletonBone('NPC UpperArm.R', 'NPC R UpperArm [RUar]', 'CME R Clavicle [RClv]', 'NPC UpperArm [Uar].R'),
SkeletonBone('NPC UpperarmTwist1.R', 'NPC R UpperarmTwist1 [RUt1]', 'CME R UpperArm [RUar]', 'NPC UpperarmTwist1 [Ut1].R'),
SkeletonBone('NPC UpperarmTwist2.R', 'NPC R UpperarmTwist2 [RUt2]', 'NPC R UpperarmTwist1 [RUt1]', 'NPC UpperarmTwist2 [Ut2].R'),
SkeletonBone('NPC Root', 'NPC Root [Root]', 'NPC', 'NPC Root [Root]'),
SkeletonBone('NPC Spine', 'NPC Spine [Spn0]', 'CME UBody [UBody]', 'NPC Spine [Spn0]'),
SkeletonBone('NPC Spine1', 'NPC Spine1 [Spn1]', 'CME Spine [Spn0]', 'NPC Spine1 [Spn1]'),
SkeletonBone('NPC Spine2', 'NPC Spine2 [Spn2]', 'CME Spine1 [Spn1]', 'NPC Spine2 [Spn2]'),
SkeletonBone('NPC Tail Thigh.L', 'NPC Tail L Thigh [LThg]', 'CME Tail L Thigh [LThg]', 'NPC Tail L Thigh [LThg]'),
SkeletonBone('NPC Tail Thigh.R', 'NPC Tail R Thigh [RThg]', 'CME Tail R Thigh [RThg]', 'NPC Tail R Thigh [RThg]'),
SkeletonBone('NPC Tail Spine', 'NPC Tail Spine [Spn0]', 'CME Tail Spine [Spn0]', 'NPC Tail Spine [Spn0]'),
SkeletonBone('NPC TailBone01', 'NPC TailBone01', 'POS TailBone01', 'NPC TailBone01'),
SkeletonBone('NPC TailBone02', 'NPC TailBone02', 'POS TailBone02', 'NPC TailBone02'),
SkeletonBone('NPC TailBone03', 'NPC TailBone03', 'POS TailBone03', 'NPC TailBone03'),
SkeletonBone('NPC TailBone04', 'NPC TailBone04', 'POS TailBone04', 'NPC TailBone04'),
SkeletonBone('NPC TailBone05', 'NPC TailBone05', 'POS TailBone05', 'NPC TailBone05'),
SkeletonBone('NPC TailBone06', 'NPC TailBone06', 'POS TailBone06', 'NPC TailBone06'),
SkeletonBone('NPC TailBone07', 'NPC TailBone07', 'POS TailBone07', 'NPC TailBone07'),
SkeletonBone('NPC TailBone08', 'NPC TailBone08', 'POS TailBone08', 'NPC TailBone08'),
SkeletonBone('NPCEyeBone', 'NPCEyeBone', 'NPC Head [Head]', 'NPCEyeBone'),
SkeletonBone('POS Tail', 'POS Tail', 'Tail Main', 'POS Tail'),
SkeletonBone('POS TailBone01', 'POS TailBone01', 'POS Tail', 'POS TailBone01'),
SkeletonBone('POS TailBone02', 'POS TailBone02', 'NPC TailBone01', 'POS TailBone02'),
SkeletonBone('POS TailBone03', 'POS TailBone03', 'NPC TailBone02', 'POS TailBone03'),
SkeletonBone('POS TailBone04', 'POS TailBone04', 'NPC TailBone03', 'POS TailBone04'),
SkeletonBone('POS TailBone05', 'POS TailBone05', 'NPC TailBone04', 'POS TailBone05'),
SkeletonBone('POS TailBone06', 'POS TailBone06', 'NPC TailBone05', 'POS TailBone06'),
SkeletonBone('POS TailBone07', 'POS TailBone07', 'NPC TailBone06', 'POS TailBone07'),
SkeletonBone('POS TailBone08', 'POS TailBone08', 'NPC TailBone07', 'POS TailBone08'),
SkeletonBone('POS TailSpine', 'POS TailSpine', 'CME Tail Spine [Spn0]', 'POS TailSpine'),
SkeletonBone('POS TailSpine1', 'POS TailSpine1', 'CME Tail Spine1 [Spn1]', 'POS TailSpine1'),
SkeletonBone('PreSHIELD', 'PreSHIELD', 'CME L Hand [LHnd]', 'PreSHIELD'),
SkeletonBone('PreWEAPON', 'PreWEAPON', 'CME R Hand [RHnd]', 'PreWEAPON'),
SkeletonBone('QUIVER', 'QUIVER', 'MOV QUIVERDefault', 'QUIVER'),
SkeletonBone('QUIVERChesko', 'QUIVERChesko', 'MOV QUIVERChesko', 'QUIVERChesko'),
SkeletonBone('QUIVERLeftHipBolt', 'QUIVERLeftHipBolt', 'MOV QUIVERLeftHipBolt', 'QUIVERLeftHipBolt'),
SkeletonBone('Reverse Axe', 'Reverse Axe', 'Weapon Pelvis', 'Reverse Axe'),
SkeletonBone('Wing1.R', 'RightWing1', 'VampireLord Wings', 'RightWing1'),
SkeletonBone('Wing2.R', 'RightWing2', 'RightWing1', 'RightWing2'),
SkeletonBone('Wing3.R', 'RightWing3', 'RightWing2', 'RightWing3'),
SkeletonBone('Wing4.R', 'RightWing4', 'RightWing3', 'RightWing4'),
SkeletonBone('Wing5.R', 'RightWing5', 'RightWing4', 'RightWing5'),
SkeletonBone('SHIELD', 'SHIELD', 'PreSHIELD', 'SHIELD'),
SkeletonBone('SWP Swords on Back', 'SWP Swords on Back', 'Weapon Spine2', 'SWP Swords on Back'),
SkeletonBone('SWP WeaponBack', 'SWP WeaponBack', 'Weapon Spine2', 'SWP WeaponBack'),
SkeletonBone('SWP WeaponBackAxeMace', 'SWP WeaponBackAxeMace', 'Weapon Spine2', 'SWP WeaponBackAxeMace'),
SkeletonBone('Schlong', 'Schlong', 'Genitals', 'Schlong'),
SkeletonBone('SchlongMagic', 'SchlongMagic', 'CME SchlongMagic', 'SchlongMagic'),
SkeletonBone('ShieldBack', 'ShieldBack', 'MOV ShieldBackDefault', 'ShieldBack'),
SkeletonBone('Skirt', 'Skirt', 'CME Pelvis [Pelv]', 'Skirt'),
SkeletonBone('SkirtBBone01', 'SkirtBBone01', 'Skirt', 'SkirtBBone01'),
SkeletonBone('SkirtBBone02', 'SkirtBBone02', 'SkirtBBone01', 'SkirtBBone02'),
SkeletonBone('SkirtBBone03', 'SkirtBBone03', 'SkirtBBone02', 'SkirtBBone03'),
SkeletonBone('SkirtFBone01', 'SkirtFBone01', 'Skirt', 'SkirtFBone01'),
SkeletonBone('SkirtFBone02', 'SkirtFBone02', 'SkirtFBone01', 'SkirtFBone02'),
SkeletonBone('SkirtFBone03', 'SkirtFBone03', 'SkirtFBone02', 'SkirtFBone03'),
SkeletonBone('SkirtBone01.L', 'SkirtLBone01', 'Skirt', 'SkirtLBone01'),
SkeletonBone('SkirtBone02.L', 'SkirtLBone02', 'SkirtLBone01', 'SkirtLBone02'),
SkeletonBone('SkirtBone03.L', 'SkirtLBone03', 'SkirtLBone02', 'SkirtLBone03'),
SkeletonBone('SkirtBone01.R', 'SkirtRBone01', 'Skirt', 'SkirtRBone01'),
SkeletonBone('SkirtBone02.R', 'SkirtRBone02', 'SkirtRBone01', 'SkirtRBone02'),
SkeletonBone('SkirtBone03.R', 'SkirtRBone03', 'SkirtRBone02', 'SkirtRBone03'),
SkeletonBone('Tail', 'Tail', 'CME Tail Pelvis [Pelv]', 'Tail'),
SkeletonBone('Tail Main', 'Tail Main', 'CME Tail Pelvis [Pelv]', 'Tail Main'),
SkeletonBone('TailBone01', 'TailBone01', 'Tail', 'TailBone01'),
SkeletonBone('TailBone02', 'TailBone02', 'CME TailBone01', 'TailBone02'),
SkeletonBone('TailBone03', 'TailBone03', 'CME TailBone02', 'TailBone03'),
SkeletonBone('TailBone04', 'TailBone04', 'CME TailBone03', 'TailBone04'),
SkeletonBone('TailBone05', 'TailBone05', 'CME TailBone04', 'TailBone05'),
SkeletonBone('Tails', 'Tails', 'CME Pelvis [Pelv]', 'Tails'),
SkeletonBone('VampireLord Wings', 'VampireLord Wings', 'CME Spine2 [Spn2]', 'VampireLord Wings'),
SkeletonBone('WEAPON', 'WEAPON', 'PreWEAPON', 'WEAPON'),
SkeletonBone('Weapon Calf.L', 'Weapon L Calf', 'CME L Knee [LKne]', 'Weapon L Calf'),
SkeletonBone('Weapon Pelvis', 'Weapon Pelvis', 'CME Pelvis [Pelv]', 'Weapon Pelvis'),
SkeletonBone('Weapon Calf.R', 'Weapon R Calf', 'CME R Knee [RKne]', 'Weapon R Calf'),
SkeletonBone('Weapon Spine1', 'Weapon Spine1', 'NPC Spine1 [Spn1]', 'Weapon Spine1'),
SkeletonBone('Weapon Spine2', 'Weapon Spine2', 'CME Spine2 [Spn2]', 'Weapon Spine2'),
SkeletonBone('WeaponAxe', 'WeaponAxe', 'MOV WeaponAxeDefault', 'WeaponAxe'),
SkeletonBone('WeaponAxe.L', 'WeaponAxeLeft', 'MOV WeaponAxeLeftDefault', 'WeaponAxeLeft'),
SkeletonBone('WeaponAxeOnBack.L', 'WeaponAxeLeftOnBack', 'MOV WeaponAxeLeftOnBack', 'WeaponAxeLeftOnBack'),
SkeletonBone('WeaponAxeReverse.L', 'WeaponAxeLeftReverse', 'MOV WeaponAxeLeftReverse', 'WeaponAxeLeftReverse'),
SkeletonBone('WeaponAxeOnBack', 'WeaponAxeOnBack', 'MOV WeaponAxeOnBack', 'WeaponAxeOnBack'),
SkeletonBone('WeaponAxeReverse', 'WeaponAxeReverse', 'MOV WeaponAxeReverse', 'WeaponAxeReverse'),
SkeletonBone('WeaponBack', 'WeaponBack', 'MOV WeaponBackDefault', 'WeaponBack'),
SkeletonBone('WeaponBackAxeMace', 'WeaponBackAxeMace', 'MOV WeaponBackAxeMaceDefault', 'WeaponBackAxeMace'),
SkeletonBone('WeaponBackAxeMaceFSM', 'WeaponBackAxeMaceFSM', 'MOV WeaponBackAxeMaceFSM', 'WeaponBackAxeMaceFSM'),
SkeletonBone('WeaponBackAxeMaceSWP', 'WeaponBackAxeMaceSWP', 'MOV WeaponBackAxeMaceSWP', 'WeaponBackAxeMaceSWP'),
SkeletonBone('WeaponBackFSM', 'WeaponBackFSM', 'MOV WeaponBackFSM', 'WeaponBackFSM'),
SkeletonBone('WeaponBackSWP', 'WeaponBackSWP', 'MOV WeaponBackSWP', 'WeaponBackSWP'),
SkeletonBone('WeaponBow', 'WeaponBow', 'MOV WeaponBowDefault', 'WeaponBow'),
SkeletonBone('WeaponBowBetter', 'WeaponBowBetter', 'MOV WeaponBowBetter', 'WeaponBowBetter'),
SkeletonBone('WeaponBowChesko', 'WeaponBowChesko', 'MOV WeaponBowChesko', 'WeaponBowChesko'),
SkeletonBone('WeaponBowFSM', 'WeaponBowFSM', 'MOV WeaponBowFSM', 'WeaponBowFSM'),
SkeletonBone('WeaponCrossBow', 'WeaponCrossBow', 'MOV WeaponCrossBowDefault', 'WeaponCrossBow'),
SkeletonBone('WeaponCrossBowChesko', 'WeaponCrossBowChesko', 'MOV WeaponCrossBowChesko', 'WeaponCrossBowChesko'),
SkeletonBone('WeaponDagger', 'WeaponDagger', 'MOV WeaponDaggerDefault', 'WeaponDagger'),
SkeletonBone('WeaponDaggerAnkle', 'WeaponDaggerAnkle', 'MOV WeaponDaggerAnkle', 'WeaponDaggerAnkle'),
SkeletonBone('WeaponDaggerBackHip', 'WeaponDaggerBackHip', 'MOV WeaponDaggerBackHip', 'WeaponDaggerBackHip'),
SkeletonBone('WeaponDagger.L', 'WeaponDaggerLeft', 'MOV WeaponDaggerLeftDefault', 'WeaponDaggerLeft'),
SkeletonBone('WeaponDaggerAnkle.L', 'WeaponDaggerLeftAnkle', 'MOV WeaponDaggerLeftAnkle', 'WeaponDaggerLeftAnkle'),
SkeletonBone('WeaponDaggerBackHip.L', 'WeaponDaggerLeftBackHip', 'MOV WeaponDaggerLeftBackHip', 'WeaponDaggerLeftBackHip'),
SkeletonBone('WeaponMace', 'WeaponMace', 'MOV WeaponMaceDefault', 'WeaponMace'),
SkeletonBone('WeaponMace.L', 'WeaponMaceLeft', 'MOV WeaponMaceLeftDefault', 'WeaponMaceLeft'),
SkeletonBone('WeaponStaff', 'WeaponStaff', 'MOV WeaponStaffDefault', 'WeaponStaff'),
SkeletonBone('WeaponStaff.L', 'WeaponStaffLeft', 'MOV WeaponStaffLeftDefault', 'WeaponStaffLeft'),
SkeletonBone('WeaponSword', 'WeaponSword', 'MOV WeaponSwordDefault', 'WeaponSword'),
SkeletonBone('WeaponSwordFSM', 'WeaponSwordFSM', 'MOV WeaponSwordFSM', 'WeaponSwordFSM'),
SkeletonBone('WeaponSword.L', 'WeaponSwordLeft', 'MOV WeaponSwordLeftDefault', 'WeaponSwordLeft'),
SkeletonBone('WeaponSwordFSM.L', 'WeaponSwordLeftFSM', 'MOV WeaponSwordLeftFSM', 'WeaponSwordLeftFSM'),
SkeletonBone('WeaponSwordHip.L', 'WeaponSwordLeftHip', 'MOV WeaponSwordLeftHip', 'WeaponSwordLeftHip'),
SkeletonBone('WeaponSwordLeftHip.L', 'WeaponSwordLeftLeftHip', 'MOV WeaponSwordLeftLeftHip', 'WeaponSwordLeftLeftHip'),
SkeletonBone('WeaponSwordNMD.L', 'WeaponSwordLeftNMD', 'MOV WeaponSwordLeftNMD', 'WeaponSwordLeftNMD'),
SkeletonBone('WeaponSwordOnBack.L', 'WeaponSwordLeftOnBack', 'MOV WeaponSwordLeftOnBack', 'WeaponSwordLeftOnBack'),
SkeletonBone('WeaponSwordSWP.L', 'WeaponSwordLeftSWP', 'MOV WeaponSwordLeftSWP', 'WeaponSwordLeftSWP'),
SkeletonBone('WeaponSwordNMD', 'WeaponSwordNMD', 'MOV WeaponSwordNMD', 'WeaponSwordNMD'),
SkeletonBone('WeaponSwordOnBack', 'WeaponSwordOnBack', 'MOV WeaponSwordOnBack', 'WeaponSwordOnBack'),
SkeletonBone('WeaponSwordSWP', 'WeaponSwordSWP', 'MOV WeaponSwordSWP', 'WeaponSwordSWP'),
]


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
	('W', 'W') #, 
	#('VampireMorph', 'VampireMorph')
	]

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
    SkeletonBone('Thigh_CBP_F_01.L', 'Thigh_CBP_L_F_01', 'Leg_Thigh_skin.L'),
    SkeletonBone('Thigh_CBP_F_02.L', 'Thigh_CBP_L_F_02', 'Thigh_CBP_F_01.L'),
    SkeletonBone('Thigh_CBP_B_01.L', 'Thigh_CBP_L_B_01', 'Leg_Thigh_skin.L'),
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
    SkeletonBone('Bone_Cloth_H_003', 'Bone_Cloth_H_003', 'Bone_Cloth_H_002'),
    SkeletonBone('Cloth_Scarf_Front_01', 'Cloth_Scarf_Front_01', 'Chest'),
    SkeletonBone('Cloth_Scarf_Front_02', 'Cloth_Scarf_Front_02', 'Cloth_Scarf_Front_01'),
    SkeletonBone('Cloth_Scarf_Rear_01', 'Cloth_Scarf_Rear_01', 'Chest'),
    SkeletonBone('Cloth_Scarf_Rear_02', 'Cloth_Scarf_Rear_02', 'Cloth_Scarf_Rear_01'),
    SkeletonBone('Cloth_Scarf_Rear_03', 'Cloth_Scarf_Rear_03', 'Cloth_Scarf_Rear_02'),
    ]

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
    ('LwrLipRollIn', 'LwrLipRollIn'),
    ('Tongue', 'Tongue'),
    ('LookUp', 'LookUp'),
    ('LookDown', 'LookDown'),
    ('LookLeft', 'Look.L'),
    ('LookRight', 'Look.R')
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
        return candidates

class FO4FacebonesDict(FO4BoneDict):
    def matches(self, bone_list):
        return len([b for b in bone_list if b.startswith('skin_bone_')])

fo4Dict = FO4BoneDict(fo4Bones, fo4Expressions, fo4Parts, fo4BoneIDs)
fo4FaceDict = FO4FacebonesDict(fo4FaceBones, fo4Expressions, fo4Parts, fo4BoneIDs)

gameSkeletons = {
    'SKYRIM': skyrimDict,
    'SKYRIMSE': skyrimDict,
    'FO4': fo4Dict,
    'FO76': fo4Dict,
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
    # Better tested in blender_tests.py
    #
    # print("--Can split verts of a triangularized plane")
    # # Verts 4 & 5 are on a seam
    # verts = [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (-1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)]
    # weights = [{0: 0.4},
    #            {0: 0.6},
    #            {0: 1.0},
    #            {0: 0.8},
    #            {0: 0.3},
    #            {0: 0.1}]
    # loops = [1, 5, 4,
    #          4, 2, 0,
    #          1, 3, 5,
    #          4, 5, 2]
    # norms = [(0.0, 0.0, 2.0), (0.0, 0.0, 6.0), (0.0, 0.0, 5.0), 
    #          (0.0, 0.0, 5.0), (0.0, 0.0, 3.0), (0.0, 0.0, 1.0), 
    #          (0.0, 0.0, 2.0), (0.0, 0.0, 4.0), (0.0, 0.0, 6.0),
    #          (0.0, 0.0, 5.0), (0.0, 0.0, 6.0), (0.0, 0.0, 3.0)]
    # #norms = [(0.0, 0.0, 1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 3.0), 
    # #         (0.0, 0.0, 4.0), (0.0, 0.0, 5.0), (0.0, 0.0, 6.0)
    # #         ]
    # uvs = [(0.9, 0.1), (0.6, 0.9), (0.6, 0.1),
    #        (0.4, 0.1), (0.1, 0.9), (0.1, 0.1),
    #        (0.9, 0.1), (0.9, 0.9), (0.6, 0.9),
    #        (0.4, 0.1), (0.4, 0.9), (0.1, 0.9)]

    # morphdict = {}
    # morphdict["by2"] = [(v[0]*2, v[1]*2, v[2]*2) for v in verts]
    # morphdict["by3"] = [(v[0]*3, v[1]*3, v[2]*3) for v in verts]
        
    # # mesh_split_by_uv() splits the mesh along UV seams--any vert that has two 
    # # different UV locations needs to be split
    # mesh_split_by_uv(verts, norms, loops, uvs, weights, morphdict)

    # # Vert 5 got split into 5 & 7. Data should be the same.
    # assert len(verts) == 8, "Error: wrong number of verts after edge splitting"
    # assert len(norms) == len(loops), "Error: Count of normals shouldn't change"
    # assert len(weights) == 8, "Error: wrong number of weights after edge splitting"
    # assert len(morphdict["by2"]) == 8, "Error wrong number of verts in morph after splitting"
    # assert len(morphdict["by3"]) == 8, "Error wrong number of verts in morph after splitting"
    # assert verts.count((0.0, 1.0, 0.0)) == 2, "Error: Duplicating vert on seam"
    # assert verts.count((0.0, -1.0, 0.0)) == 2, "Error: Duplicating vert on seam"
    # assert morphdict["by3"].count((0.0, -3.0, 0.0)) == 2, "Error: Duplicating vert on seam in morph"
    # assert verts[5] == verts[7], "Error: Duplicating vert 5 to vert 7"
    # assert weights[5] == weights[7], "Error: Duplicating weights correctly"
    # # Any loop entry referencing vert 5 should have same UV location as one referencing 7
    # assert loops[1] == 5 and loops[10] == 7 and uvs[1] != uvs[10], "Error: Duplicating UV locations correctly"


    print("""####################################################################################
    Game skeletons translate to and from blender conventions. This allows blender mirror operations
    to be smart.
    """)

    assert gameSkeletons["SKYRIM"].byPynifly['NPC Finger11.L'].nif == 'NPC L Finger11 [LF11]', "Error: Bone not translated correctly"
    assert gameSkeletons["SKYRIM"].byNif['NPC L Finger11 [LF11]'].blender == 'NPC Finger11.L', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byPynifly['Arm_Finger13.R'].nif == 'RArm_Finger13', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byNif['RArm_Finger13'].blender == 'Arm_Finger13.R', "Error: Bone not translated correctly"
    assert gameSkeletons["FO4"].byPynifly['Arm_Finger51.R'].parent == gameSkeletons["FO4"].byPynifly['Arm_Hand.R'], "Error: Parents not correct"
    assert gameSkeletons["SKYRIM"].blender_name('NPC L Finger20 [LF20]') == 'NPC Finger20.L', "Error: Name translation incorrect"
    assert gameSkeletons["SKYRIM"].nif_name('NPC Finger20.L') == 'NPC L Finger20 [LF20]', "Error: Name translation incorrect"
    assert gameSkeletons["FO4"].nif_name('FOOBAR') == 'FOOBAR', "Error: Name translation incorrect"
    

    # ####################################################################################
    print(
        """
        gameSkeleton matches() function counts the bones that match bones inf the given set
        """)
    print("--Can get count of matching bones from skeleton")
    assert gameSkeletons["FO4"].matches(set(['Leg_Calf.R', 'Leg_Calf_skin.R', 'Leg_Calf_Low_skin.R', 'FOO'])) == 3, "Error: Skeletons should return correct bone match"


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
    
    flst = extend_filenames(r"C:\Users\hughr\OneDrive\SkyrimDev\Textures\\",
                            "textures",
                            [r"textures\actors\character\male\MaleHead.dds",
                             r"textures\actors\character\male\MaleHead_msn.dds",
                             "",
                             "",
                             r"textures\actors\character\male\MaleHead_sk.dds"])
    assert flst[0].upper() == r"C:\Users\hughr\OneDrive\SkyrimDev\Textures\actors\character\male\MaleHead.dds".upper(), \
    f"Have correct filepath: {flst}"

    print(">>> Can truncate a fliename to a given root")
    str1 = "C:/mod/stuff/meshes/foo/bar/mesh.tri"
    fn = truncate_filename(str1, "meshes")
    assert fn == "foo/bar/mesh.tri"
    fn2 = truncate_filename(str1, "fribble")
    assert fn2 == str1


    # ####################################################################################
    print ("""
        BoneDict expression_filter returns just the expression morphs for the given game
        BoneDict chargen_filter returns just the chargen morphs for the given game.
            Note for FO4 these aren't predefined, but match *type#. 
        """)
    exprmorphs = set(['DialogueAnger', 'MoodFear', 'CombatShout', 'RUprLipDn', 'UprLidUp.R', 'RUprLidDn', 'Smile.L'])
    assert fo4Dict.expression_filter(exprmorphs) == set(['RUprLipDn', 'UprLidUp.R', 'RUprLidDn', 'Smile.L']), "ERROR: FO4 expression filter incorrect"
    assert skyrimDict.expression_filter(exprmorphs) == set(['DialogueAnger', 'MoodFear', 'CombatShout']), "ERROR: Skyrim expression filter incorrect"
    # Chargen filter selects all non-expression morphs.
    chargenset = fo4Dict.chargen_filter(set(['RUprLipDn', 'UprLidUp.R', 'foo', 'barType1', 'fribble', 'Type45cat', 'aTypeB']))
    assert chargenset == set(['barType1', 'Type45cat']), f"ERROR: FO4 Chargen filter incorrect; {chargenset}"

    assert fo4Dict.morph_dic_game['Smile.L'] == 'LSmile', "ERROR: Morph not translated correctly"
    assert fo4Dict.morph_dic_game['UprLidUp.R'] == 'RUprLidUp', "ERROR: Morph not translated correctly"
    assert fo4Dict.morph_dic_blender['LUprLidUp'] == 'UprLidUp.L', "ERROR: Morph not translated correctly"
    
