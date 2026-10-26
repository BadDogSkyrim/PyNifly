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
from .bone_tables import (  # noqa: F401  -- re-exported, as before
    SkeletonBone, BodyPart,
    fnvBones, fnvExpressions, fnvParts, skyrimBones, skyrimExpressions, skyrimParts,
    fo4Bones, fo4FaceBones, fo4Expressions, fo4BoneIDs, fo4Dismember, fo4Parts,
    sfSkeletonHierarchy,)


# No basicConfig here — a library must not configure root logging (it hijacks
# the host app's config and forces DEBUG everywhere). Levels/handlers are the
# app's responsibility.
log = logging.getLogger("pynifly")


# ###################### FILE HANDLING ##################################

def texture_path(filepath:str) -> Path:
    """ 
    Clean up the given texture filepath.
    """
    if not filepath: return None
    fp = filepath.strip('"').strip("'")
    p = Path(fp)
    if p.parts[-1].lower() != 'textures':
        return p / 'textures'
    return p


def materials_path(filepath:str) -> Path:
    """ 
    Clean up the given materials filepath.
    """
    if not filepath: return None
    fp = filepath.strip('"').strip("'")
    p = Path(fp)
    if p.parts[-1].lower() != 'materials':
        return p / 'materials'
    return p


def tmp_filepath(filepath:Path, ext=None) -> Path:
    """
    Return a unique temporary filename with no embedded spaces. Name is based on the base
    name of 'filepath', with suffixes to make it unique, and given the extension 'ext'.
    """
    newfp = filepath.with_stem(filepath.stem.replace(' ', '_'))
    if not newfp.stem.startswith("tmp_"): 
        newfp = newfp.with_stem("tmp_" + newfp.stem)
    if ext:
        newfp = newfp.with_suffix(ext)

    fp = Path(tempfile.gettempdir()) / newfp.name
    # Temp file doesn't exist, we can use it without disambiguation.
    if not os.path.exists(fp):
        return fp
    
    fpbase = fp.stem
    i = 0
    iter = ""
    while i < 10000:
        iter = f"_{(int(time.time()*1000) & 0xFFFFFF):06X}"
        fp = fp.with_stem(fpbase + iter)
        if not os.path.exists(fp): break
        i += 1
    if i < 10000:
        return fp
    else:
        raise Exception("Could not create temporary file")


def nospace_filepath(filepath:Path,) -> Path:
    """
    Return the input filepath if no spaces, else a new temp filepath.
    Also remove any surrounding quotes.
    """
    # fp = filepath.strip('"').strip("'")
    if ' ' in str(filepath):
        return tmp_filepath(filepath)
    else:
        return filepath


def copyfile(fin, fout):
    fin_clean = str(fin).strip('"')
    if fin_clean != str(fout):
        shutil.copy(fin_clean, str(fout))


def tmp_copy(filepath:Path) -> Path:
    """Create a temporary copy of the file and return its filepath."""
    fp = tmp_filepath(filepath)
    copyfile(str(filepath), str(fp))
    return fp


def tmp_copy_nospace(filepath:Path) -> Path:
    """
    If the filepath contains spaces, create a temporary copy of the file and return its
    filepath. Otherwise just return the original.
    """
    if ' ' in str(filepath):
        return tmp_copy(filepath)
    else:
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


def find_referenced_file(filepath:str, nifpath:str, root='textures', alt_suffix=None, alt_pathlist=None) -> str:
    """
    Look for a texture file with either a PNG or DDS extension.
    filepath may or may not be absolute. If relative, may or may not start with "textures".
    if relative, look in basedir/textures. If not there, look in blender's texture directory.
    Look for both the dds and png extension.
    Return the path if found, else None.
    """
    fp = Path(filepath.lower())

    # If relative, must start with `root` ("textures" or "materials"). If the
    # path contains `root` as a non-leading component (e.g. "Data/materials/...")
    # truncate to start at `root`. Otherwise prepend `root`.
    if not fp.is_absolute():
        if root in fp.parts and fp.parts[0] != root:
            fp = Path(*fp.parts[fp.parts.index(root):])
        elif fp.parts[0] != root:
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

    # Not found, look in alternative texture directories
    for alt_path in alt_pathlist or []:
        if alt_path:
            bd = Path(alt_path)
            if bd.name.lower() == 'textures':
                bd = bd.parent
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

    # Look for BODYTRI string extra data on the root node
    ed = nif.rootNode.get_extra_data(name='BODYTRI', blockname='NiStringExtraData')
    if ed:
        v = ed.string_data
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
    m = re.match(r"(.+)\.\d+\Z", n)
    if m:
        return m[1]
    return n



class BoneDict:
    def __init__(self, bone_list, morph_list, part_list, dismem_list=None, use_niftools=False):
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

        if isinstance(part_list, dict):
            self.parts = part_list
        else:
            for p in part_list:
                self.parts[p.name] = p
        # NB the test below read `type(dismem_list == dict)` -- a misplaced paren, so it
        # was always truthy and the else branch was dead. Games passing a list (or taking
        # the default) got a list where lines below use dismem as a dict.
        if dismem_list is None:
            dismem_list = {}
        if isinstance(dismem_list, dict):
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





fnvDict = BoneDict(fnvBones, fnvExpressions, fnvParts)





skyrimDict = BoneDict(skyrimBones, skyrimExpressions, skyrimParts)







fo4chargen_pat = re.compile("Type[0-9]+")

class FO4BoneDict(BoneDict):
    def chargen_filter(self, candidates):
        return candidates

class FO4FacebonesDict(FO4BoneDict):
    def matches(self, bone_list):
        return len([b for b in bone_list if b.startswith('skin_bone_')])

fo4Dict = FO4BoneDict(fo4Bones, fo4Expressions, fo4Parts, fo4BoneIDs)
fo4FaceDict = FO4FacebonesDict(fo4FaceBones, fo4Expressions, fo4Parts, fo4BoneIDs)

# ----------------------- Starfield skeleton -----------------------
# Starfield bone names carry an L_/R_/C_ prefix for the left/right/centre side of a
# symmetric skeleton (L_Thigh, R_Calf, C_Spine) plus unprefixed utility bones
# (COM, Root, WEAPON...). We convert the side PREFIX to a Blender-friendly .L/.R/.C
# SUFFIX so Blender's mirror/symmetry tools work and the names read naturally. The
# conversion is a pure rule, so it also covers modder-added bones (L_Tail_01 ->
# Tail_01.L) and round-trips exactly. Unprefixed bones pass through unchanged.
_SF_SIDE_PREFIX = (('L_', '.L'), ('R_', '.R'), ('C_', '.C'))

def sf_blender_bone_name(nif_name):
    """Starfield nif bone name -> Blender bone name (side prefix -> .L/.R/.C suffix)."""
    for pre, suf in _SF_SIDE_PREFIX:
        if nif_name.startswith(pre):
            return nif_name[len(pre):] + suf
    return nif_name

def sf_nif_bone_name(blender_name):
    """Blender bone name -> Starfield nif bone name (reverse of sf_blender_bone_name).
    Strips Blender's '.001' duplicate suffix first."""
    base = blender_basename(blender_name)
    for pre, suf in _SF_SIDE_PREFIX:
        if base.endswith(suf):
            return pre + base[:-len(suf)]
    return base

class SFBoneDict(BoneDict):
    """Starfield bone dictionary. Name conversion is rule-based (L_/R_/C_ <-> .L/.R/.C)
    so it covers vanilla and modder-added bones alike; the dict is also seeded with the
    full vanilla skeleton (below) for hierarchy / introspection."""
    def blender_name(self, nif_name):
        if self.use_niftools and nif_name in self.byNif:
            return self.byNif[nif_name].niftools
        return sf_blender_bone_name(nif_name)

    def nif_name(self, blender_name):
        return sf_nif_bone_name(blender_name)


def _build_sf_bones(hierarchy):
    return [SkeletonBone(sf_blender_bone_name(n),
                         n,
                         (sf_blender_bone_name(p) if p else None))
            for n, p in hierarchy]

sfDict = SFBoneDict(_build_sf_bones(sfSkeletonHierarchy), [], [])

gameSkeletons = {
    'SKYRIM': skyrimDict,
    'SKYRIMSE': skyrimDict,
    'FO4': fo4Dict,
    'FO76': fo4Dict,
    'FO3': fnvDict,
    'FONV': fnvDict,
    'SF': sfDict}
