"""Starfield material database (`.cdb`) reader.

Starfield compiles every material into one binary database, `materialsbeta.cdb` (inside
`Starfield - Materials.ba2`), keyed by the CRC hash of each material's path. This module reads
that database directly and reconstructs individual materials as loose `.mat` JSON -- the same
format PyNifly's sf_materials parser consumes -- so importing a Starfield nif can resolve its
material without any external exporter.

It's a port of the reader in maximusmaxy/MaxieStarfieldScripts (`include/cdb.h`, `src/crc.cpp`),
which is the engine behind the Starfield Material Exporter. Pure Python (no Blender, no DLL) so it
runs standalone from the command line AND can be called from PyNifly.

The cdb is a self-describing `BSComponentDB2` reflection database:
  BETH header -> string table -> class/type registry (each class = fields with type refs)
  -> CompiledDB (resource-id -> db-id hash map) -> file index (objects, components, edges)
  -> per-component data ("diffs" against parent/default), read via the reflection registry.
A material is rebuilt by hashing its path to a resource id, finding its object, composing its
parent chain, and following child-object references (layers -> materials -> texture sets -> files).
"""

import struct
import sys

_DEBUG = False

# ---------------------------------------------------------------------------
# CRC-32 path hashing (crc.cpp): standard reflected CRC-32 table, init 0, no final XOR,
# with each char lower-cased and '/' folded to '\' before hashing.
# ---------------------------------------------------------------------------

def _make_crc_table():
    tbl = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if (c & 1) else (c >> 1)
        tbl.append(c & 0xFFFFFFFF)
    return tbl

_CRC_TABLE = _make_crc_table()


def _xform(ch):
    o = ord(ch)
    if 0x41 <= o <= 0x5A:   # A-Z -> a-z
        o += 0x20
    elif ch == '/':
        o = 0x5C            # '/' -> '\'
    return o


def crc32(s):
    """The game's path CRC (init 0, no final xor, lower+backslash transform per char)."""
    result = 0
    for ch in s:
        result = _CRC_TABLE[(_xform(ch) ^ result) & 0xFF] ^ (result >> 8)
    return result & 0xFFFFFFFF


def _ext_uint32(ext):
    """Pack up to 4 extension chars (no dot) little-endian, e.g. 'mat' -> 0x0074616D."""
    v = 0
    for i, ch in enumerate(ext[:4]):
        v |= (ord(ch) & 0xFF) << (8 * i)
    return v


def resource_id_from_path(path):
    """(dir_crc, file_crc, ext_uint32) for a material path like 'Materials\\...\\X.mat'."""
    p = path.replace('/', '\\')
    slash = p.rfind('\\')
    dot = p.rfind('.')
    if dot < 0:
        dot = len(p)
    if slash >= 0:
        dir_crc = crc32(p[:slash])
        file_crc = crc32(p[slash + 1:dot])
    else:
        dir_crc = crc32(p)
        file_crc = crc32(p)
    ext = _ext_uint32(p[dot + 1:]) if dot < len(p) else 0
    return (dir_crc, file_crc, ext)


# ---------------------------------------------------------------------------
# TypeRef builtins (cdb.h)
# ---------------------------------------------------------------------------
T_NULL = 0xFFFFFF01
T_STRING = 0xFFFFFF02
T_LIST = 0xFFFFFF03
T_MAP = 0xFFFFFF04
T_REF = 0xFFFFFF05
T_INT8 = 0xFFFFFF08
T_UINT8 = 0xFFFFFF09
T_INT16 = 0xFFFFFF0A
T_UINT16 = 0xFFFFFF0B
T_INT32 = 0xFFFFFF0C
T_UINT32 = 0xFFFFFF0D
T_INT64 = 0xFFFFFF0E
T_UINT64 = 0xFFFFFF0F
T_BOOL = 0xFFFFFF10
T_FLOAT = 0xFFFFFF11
T_DOUBLE = 0xFFFFFF12

def _is_builtin(ref):
    return (ref & 0xFFFFFF00) == 0xFFFFFF00

def _is_chunk_type(ref):
    return ref == T_LIST or ref == T_MAP

# Chunk signatures (4 ASCII bytes read as little-endian uint32).
def _sig(s):
    return struct.unpack('<I', s)[0]
SIG_BETH = _sig(b'BETH')
SIG_OBJT = _sig(b'OBJT')
SIG_USER = _sig(b'USER')
SIG_DIFF = _sig(b'DIFF')
SIG_USRD = _sig(b'USRD')
SIG_MAPC = _sig(b'MAPC')
SIG_LIST = _sig(b'LIST')
SIG_STRT = _sig(b'STRT')

EXT_MAT = _ext_uint32('mat')   # 0x0074616D

_PRIM = {
    T_INT8: ('<b', 1), T_UINT8: ('<B', 1), T_INT16: ('<h', 2), T_UINT16: ('<H', 2),
    T_INT32: ('<i', 4), T_UINT32: ('<I', 4), T_INT64: ('<q', 8), T_UINT64: ('<Q', 8),
    T_FLOAT: ('<f', 4), T_DOUBLE: ('<d', 8),
}

# Component types whose Data.ID references another object (a layer / material / texture set /
# etc.) -- these drive the object graph traversal during reconstruction.
_ID_TYPES = {
    'BSMaterial::BlenderID', 'BSMaterial::LayerID', 'BSMaterial::MaterialID',
    'BSMaterial::TextureSetID', 'BSMaterial::UVStreamID', 'BSMaterial::LODMaterialID',
    'BSMaterial::LayeredMaterialID',
}

# Well-known root/template materials, for resolving the "Parent" field.
_ROOT_MATERIAL_PATHS = [
    'materials\\layered\\root\\materials.mat',
    'materials\\layered\\root\\blenders.mat',
    'materials\\layered\\root\\texturesets.mat',
    'materials\\layered\\root\\uvstreams.mat',
    'materials\\layered\\root\\layers.mat',
    'materials\\layered\\root\\layeredmaterials.mat',
]


def _fmt_res_id(pid):
    return f"res:{pid[0]:08X}:{pid[1]:08X}:{pid[2]:08X}"


def _compose(lhs, rhs):
    """Deep-merge rhs into lhs (descendant overrides ancestor), matching ComposeJsons."""
    if isinstance(rhs, dict):
        if not rhs:
            return
        for k, v in rhs.items():
            if isinstance(v, (dict, list)):
                if k not in lhs or not isinstance(lhs[k], type(v)):
                    lhs[k] = type(v)()
                _compose(lhs[k], v)
            else:
                lhs[k] = v
    elif isinstance(rhs, list):
        for i, v in enumerate(rhs):
            while len(lhs) <= i:
                lhs.append(None)
            if isinstance(v, (dict, list)):
                if not isinstance(lhs[i], type(v)):
                    lhs[i] = type(v)()
                _compose(lhs[i], v)
            elif v is not None:
                lhs[i] = v


class _ObjectQueue:
    """De-duplicating FIFO of referenced object dbids to expand, matching ObjectQueue."""
    def __init__(self):
        self.seen = {}          # dbid -> local id
        self.pending = []       # dbids still to expand
        self._next = 1
    def push(self, dbid):
        if dbid not in self.seen:
            self.seen[dbid] = self._next
            self._next += 1
            self.pending.append(dbid)
    def pop(self):
        return self.pending.pop(0)


class _Class:
    __slots__ = ('name_ref', 'type_id', 'flags', 'fields')
    def __init__(self, name_ref, type_id, flags, fields):
        self.name_ref = name_ref      # StringRef offset
        self.type_id = type_id
        self.flags = flags            # bit2=User, bit3=Struct
        self.fields = fields          # list of (name_ref, type_ref, offset, size)
    def is_user(self):
        return bool(self.flags & (1 << 2))


class CdbFile:
    """Parses a Starfield materialsbeta.cdb and reconstructs materials as .mat JSON dicts."""

    def __init__(self, data):
        self.d = data
        self.p = 0
        self.string_table = b''
        self.classes = []                 # list[_Class]
        self.class_by_nameref = {}        # StringRef offset -> _Class
        self.build_version = ''
        # file index
        self.component_types = []         # list[(idx, class_name, version, is_empty)]
        self.objects = []                 # list[dict(pid=(d,f,e), dbid, parent, has_data)]
        self.components = []              # list[(object_id, index, type)]
        self.edges = []                   # list[(src, tgt, index, type)]
        self.object_by_dbid = {}
        self.resource_to_db = {}          # (dir,file,ext) -> dbid
        self.component_map = {}           # dbid -> [(global_index, comp_index, comp_type)]
        self._pos_map = None              # per-component stream offset (built lazily)
        self._comp_cache = {}             # global_index -> parsed component json
        self._id_to_path = {}             # dbid -> known .mat path (for Parent resolution)
        self._parse_header()

    # --- low-level readers ---
    def _u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def _u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2; return v
    def _u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
    def _u64(self):
        v = struct.unpack_from('<Q', self.d, self.p)[0]; self.p += 8; return v
    def _bytes(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v
    def _str(self):
        n = self._u16()
        if n == 0:
            return ''
        raw = self._bytes(n)          # n bytes incl. trailing null
        return raw[:n - 1].decode('utf-8', 'replace')
    def _chunk(self):
        sig = self._u32(); size = self._u32(); return sig, size
    def _res_id(self):
        # BSResource::ID reads as file, ext, dir; stored as (dir, file, ext).
        f = self._u32(); e = self._u32(); di = self._u32()
        return (di, f, e)

    def _string_at(self, ref):
        end = self.string_table.find(b'\x00', ref)
        return self.string_table[ref:end].decode('utf-8', 'replace')

    def type_name(self, ref):
        if _is_builtin(ref):
            return _BUILTIN_NAMES.get(ref, 'builtin')
        return self._string_at(ref)

    # --- header + index ---
    def _parse_header(self):
        sig = self._u32()
        if sig != SIG_BETH:
            raise ValueError(f"Not a cdb file (magic {sig:08X})")
        _size = self._u32()
        self.version = self._u32()
        _chunk_count = self._u32()

        # string table
        _ssig, ssize = self._chunk()
        self.string_table = self._bytes(ssize)

        # class/type registry
        _tsig, _tsize = self._chunk()
        type_count = self._u32()
        for _ in range(type_count):
            self._chunk()
            name_ref = self._u32()
            type_id = self._u32()
            flags = self._u16()
            field_count = self._u16()
            fields = []
            for _ in range(field_count):
                fn = self._u32(); ft = self._u32(); fo = self._u16(); fs = self._u16()
                fields.append((fn, ft, fo, fs))
            cls = _Class(name_ref, type_id, flags, fields)
            self.classes.append(cls)
            self.class_by_nameref[name_ref] = cls

        if _DEBUG:
            print(f"[dbg] after types: pos={self.p:#x} type_count={type_count} "
                  f"strtable={len(self.string_table)}")
        # two db chunks: CompiledDB (hash map) + DBFileIndex (objects/components/edges)
        for _ in range(2):
            self._chunk()
            ref = self._u32()
            name = self.type_name(ref)
            if _DEBUG:
                print(f"[dbg] db chunk '{name}' at pos={self.p:#x}")
            if name == 'BSMaterial::Internal::CompiledDB':
                self._read_compiled_db()
            elif name == 'BSComponentDB2::DBFileIndex':
                self._read_file_index()
            else:
                raise ValueError(f"Unknown db chunk type: {name}")

        self.component_data_start = self.p   # component "diff" blobs follow the file index

        for o in self.objects:
            self.object_by_dbid[o['dbid']] = o
            if o['pid'][2] == EXT_MAT:
                self.resource_to_db[o['pid']] = o['dbid']

        for gi, (oid, idx, typ) in enumerate(self.components):
            self.component_map.setdefault(oid, []).append((gi, idx, typ))

        # Seed Parent resolution with the well-known root/template materials.
        for rp in _ROOT_MATERIAL_PATHS:
            dbid = self.material_dbid(rp)
            if dbid:
                self._id_to_path[dbid] = rp

    def _read_vector_header(self):
        """A serialized vector = Chunk(8) + List{type(u32), size(u32)}; returns count."""
        self._chunk()
        _elem_type = self._u32()
        return self._u32()

    def _read_compiled_db(self):
        self.build_version = self._str()
        self._u32()  # pad
        # HashMap: vector<pair<BSResource::ID, uint64>>
        n = self._read_vector_header()
        for _ in range(n):
            self._res_id(); self._u64()
        # Collisions: vector<FilePair{ID First, ID Second}>
        n = self._read_vector_header()
        for _ in range(n):
            self._res_id(); self._res_id()
        # Circular: vector<nullptr_t> (elements read nothing)
        self._read_vector_header()

    def _read_file_index(self):
        self._u8()               # Optimized (bool)
        self._u32()              # pad
        # typeVec: vector<pair<uint16, TypeInfoPartial{version u16, isEmpty bool}>>
        n = self._read_vector_header()
        type_meta = []
        for _ in range(n):
            key = self._u16()
            version = self._u16()
            is_empty = self._u8()
            type_meta.append((key, version, is_empty))
        for (key, version, is_empty) in type_meta:
            self._chunk()
            self._u32(); self._u32()   # User{target, casted}
            class_name = self._str()
            self._u32()                # pad
            self.component_types.append((key, class_name, version, is_empty))
        # Objects. cdb v4 grew ObjectInfo to 33 bytes: it stores the parent's full resource
        # ID (12 bytes) after the parent DBID -- PersistentID(12) + DBID(4) + ParentDBID(4)
        # + ParentPersistentID(12) + HasData(1). (The older 21-byte layout read by
        # maximusmaxy/SFME is why that tool misaligns and runs away on a v4 cdb.)
        n = self._read_vector_header()
        if _DEBUG:
            print(f"[dbg] file index: {len(self.component_types)} types, objects n={n} at pos={self.p:#x}")
        for _ in range(n):
            pid = self._res_id()
            dbid = self._u32()
            parent = self._u32()
            self._res_id()            # parent's resource id (v4), not needed
            has_data = self._u8()
            self.objects.append({'pid': pid, 'dbid': dbid, 'parent': parent,
                                 'has_data': has_data})
        # Components
        n = self._read_vector_header()
        if _DEBUG:
            print(f"[dbg] objects done pos={self.p:#x}, components n={n}")
        for _ in range(n):
            oid = self._u32(); idx = self._u16(); typ = self._u16()
            self.components.append((oid, idx, typ))
        # Edges
        n = self._read_vector_header()
        for _ in range(n):
            src = self._u32(); tgt = self._u32(); idx = self._u16(); typ = self._u16()
            self.edges.append((src, tgt, idx, typ))

    # --- lookup ---
    def material_dbid(self, path):
        """The db object id for a material path, or None if not present."""
        return self.resource_to_db.get(resource_id_from_path(path))

    # --- reflection component reader ---------------------------------------
    # Each component's data is a "diff" blob: a main OBJT/DIFF chunk that recursively reads
    # the component class's fields, with List/Map fields and User-cast fields deferred to
    # following LIST/MAPC/USER chunks (LIFO queues), matching cdb.h ReadNextObject.
    # container is a dict/list to store into, or None to skip (advance bytes only).

    def _read_prim(self, ref):
        fmt, size = _PRIM[ref]
        v = struct.unpack_from(fmt, self.d, self.p)[0]
        self.p += size
        return v

    def _read_type(self, container, key, ref, is_diff, is_cast=False):
        store = container is not None
        if ref == T_NULL:
            if store: container[key] = None
            return
        if ref == T_STRING:
            s = self._str()
            if store: container[key] = s
            return
        if ref == T_BOOL:
            b = self._u8()
            if store: container[key] = "true" if b else "false"
            return
        if ref in _PRIM:
            v = self._read_prim(ref)
            if store: container[key] = str(v)
            return
        if ref == T_REF:
            subref = self._u32()
            if _is_builtin(subref):
                if store: container[key] = None
                return
            v = {"Type": "<ref>", "Data": None} if store else None
            if store: container[key] = v
            cls = self.class_by_nameref.get(subref)
            if cls is not None and cls.is_user():
                self._user_queue.append((v, "Data"))
            else:
                self._read_type(v, "Data", subref, is_diff)
            return

        name = self._string_at(ref)
        if name == "BSComponentDB2::ID":
            if not is_diff:
                idv = self._u32()
            else:
                self._u16(); idv = self._u32(); self._u16()
            if store: container[key] = str(idv) if idv != 0 else ""
            return

        cls = self.class_by_nameref.get(ref)
        if cls is None:
            raise ValueError(f"cdb: type not found {ref:#x} ({name})")
        if (not is_cast) and cls.is_user():
            self._user_queue.append((container, key))
            return

        v = {"Type": name, "Data": {}} if store else None
        data = v["Data"] if store else None
        if store: container[key] = v
        if not is_diff:
            for (fn, ft, _fo, _fs) in cls.fields:
                fname = self._string_at(fn)
                if _is_chunk_type(ft):
                    if store: data[fname] = None
                    self._chunk_queue.append((data, fname, is_diff))
                else:
                    self._read_type(data, fname, ft, is_diff)
        else:
            idx = self._u16()
            while idx != 0xFFFF:
                fn, ft, _fo, _fs = cls.fields[idx]
                fname = self._string_at(fn)
                if _is_chunk_type(ft):
                    if store: data[fname] = None
                    self._chunk_queue.append((data, fname, is_diff))
                else:
                    self._read_type(data, fname, ft, is_diff)
                idx = self._u16()

    def _read_list(self, container, key, is_diff):
        elem_type = self._u32()
        size = self._u32()
        store = container is not None
        coll = None
        if store:
            coll = {"Type": "<collection>"}
            container[key] = coll
        if size:
            data = []
            if store:
                coll["ElementType"] = self.type_name(elem_type)
                coll["Data"] = data
            for i in range(size):
                if store:
                    data.append(None)
                    self._read_type(data, i, elem_type, is_diff)
                else:
                    self._read_type(None, i, elem_type, is_diff)
        elif store:
            coll["Data"] = []

    def _read_map(self, container, key, is_diff):
        ktype = self._u32(); vtype = self._u32(); size = self._u32()
        store = container is not None
        coll = None
        if store:
            coll = {"Type": "<collection>", "ElementType": "StdMapType::Pair", "Data": []}
            container[key] = coll
        for _ in range(size):
            if _is_builtin(ktype):
                keystr = self._read_map_key(ktype)
                if store:
                    pd = {"Key": keystr, "Value": None}
                    coll["Data"].append({"Type": "StdMapType::Pair", "Data": pd})
                    self._read_type(pd, "Value", vtype, is_diff)
                else:
                    self._read_type(None, "Value", vtype, is_diff)
            else:
                # only BSResource::ID keys occur; read file,ext,dir
                self._res_id()
                self._read_type(coll["Data"] if store else None,
                                len(coll["Data"]) if store else None, vtype, is_diff)

    def _read_map_key(self, ref):
        if ref == T_STRING:
            return self._str()
        if ref == T_BOOL:
            return "true" if self._u8() else "false"
        return str(self._read_prim(ref))

    def _read_one_chunk(self, container, key):
        sig, _size = self._chunk()
        if sig == SIG_OBJT or sig == SIG_DIFF:
            ref = self._u32()
            self._read_type(container, key, ref, sig == SIG_DIFF)
        elif sig == SIG_USER or sig == SIG_USRD:
            ucont, ukey = self._user_queue.pop()
            _target = self._u32(); casted = self._u32()
            self._read_type(ucont, ukey, casted, sig == SIG_USRD, is_cast=True)
            self._u32()   # userValue
        elif sig == SIG_LIST or sig == SIG_MAPC:
            ccont, ckey, cdiff = self._chunk_queue.pop()
            if sig == SIG_LIST:
                self._read_list(ccont, ckey, cdiff)
            else:
                self._read_map(ccont, ckey, cdiff)
        else:
            raise ValueError(f"cdb: unknown chunk sig {sig:#x} at {self.p:#x}")

    def _read_component(self, store):
        self._chunk_queue = []
        self._user_queue = []
        holder = {}
        self._read_one_chunk(holder if store else None, 'v')
        while self._chunk_queue or self._user_queue:
            self._read_one_chunk(None, None)
        return holder.get('v') if store else None

    def _ensure_pos_map(self):
        """Skip-scan the component-data region once to record each component's byte offset,
        so individual components can be parsed on demand without holding 1.4M of them."""
        if self._pos_map is not None:
            return
        self.p = self.component_data_start
        pm = []
        for _ in range(len(self.components)):
            pm.append(self.p)
            self._read_component(store=False)
        self._pos_map = pm

    def _component_json(self, gi):
        c = self._comp_cache.get(gi)
        if c is None:
            self.p = self._pos_map[gi]
            c = self._read_component(store=True)
            self._comp_cache[gi] = c
        return c

    # --- material reconstruction (cdb.h Manager::CreateMaterialJson) --------
    def _parent_list(self, dbid):
        out = [dbid]
        o = self.object_by_dbid.get(dbid)
        while o and o['parent'] != 0:
            out.append(o['parent'])
            o = self.object_by_dbid.get(o['parent'])
        return out

    def _indexed_component(self, components_list, db_type, index):
        for m in components_list:
            if m.get('Index') == index and m.get('Type', '').lower() == db_type.lower():
                return m
        m = {'Type': db_type, 'Index': index, 'Data': {}}
        components_list.append(m)
        return m

    def _get_full_json(self, dbid, obj):
        comps = []
        obj['Components'] = comps
        for anc in reversed(self._parent_list(dbid)):
            for (gi, cidx, _ctyp) in self.component_map.get(anc, []):
                dbval = self._component_json(gi)
                if not dbval or 'Type' not in dbval:
                    continue
                cval = self._indexed_component(comps, dbval['Type'], cidx)
                _compose(cval['Data'], dbval.get('Data'))

    def _set_material_parent(self, obj, dbid):
        for parent in self._parent_list(dbid)[1:]:
            p = self._id_to_path.get(parent)
            if p:
                obj['Parent'] = p
                return

    def _get_referenced_ids(self, comp, queue):
        if comp.get('Type') in _ID_TYPES:
            data = comp.get('Data')
            idstr = data.get('ID') if isinstance(data, dict) else None
            if idstr:
                dbid = int(idstr)
                o = self.object_by_dbid.get(dbid)
                if o:
                    queue.push(dbid)
                    data['ID'] = _fmt_res_id(o['pid'])
        else:
            data = comp.get('Data')
            if isinstance(data, dict):
                for m in data.values():
                    if isinstance(m, dict) and 'Type' in m:
                        self._get_referenced_ids(m, queue)

    def get_material(self, path):
        """Reconstruct a material as a .mat-style dict {Version, Objects:[...]}, or None."""
        matid = self.material_dbid(path)
        if not matid:
            return None
        self._ensure_pos_map()
        # so this material's own path resolves as a Parent for its children.
        self._id_to_path.setdefault(matid, path)
        result = {'Version': 1, 'Objects': []}
        queue = _ObjectQueue()
        queue.seen[matid] = 0

        matobj = {}
        self._get_full_json(matid, matobj)
        self._set_material_parent(matobj, matid)
        for c in matobj['Components']:
            self._get_referenced_ids(c, queue)
        result['Objects'].append(matobj)

        while queue.pending:
            dbid = queue.pop()
            o = self.object_by_dbid.get(dbid)
            obj = {}
            if o:
                obj['ID'] = _fmt_res_id(o['pid'])
                self._get_full_json(dbid, obj)
                self._set_material_parent(obj, dbid)
                for c in obj['Components']:
                    self._get_referenced_ids(c, queue)
            result['Objects'].append(obj)
        return result


_BUILTIN_NAMES = {
    T_NULL: '<null>', T_STRING: 'BSFixedString', T_LIST: '<collection>', T_MAP: '<collection>',
    T_REF: 'pointer', T_INT8: 'int8_t', T_UINT8: 'uint8_t', T_INT16: 'int16_t',
    T_UINT16: 'uint16_t', T_INT32: 'int32_t', T_UINT32: 'uint32_t', T_INT64: 'int64_t',
    T_UINT64: 'uint64_t', T_BOOL: 'bool', T_FLOAT: 'float', T_DOUBLE: 'double',
}


import json
import os


def load_cdb(path):
    """Parse a materialsbeta.cdb file. The returned CdbFile can extract materials by path
    via get_material(path) -> .mat dict (or None). Reusable across many materials."""
    with open(path, 'rb') as f:
        return CdbFile(f.read())


def extract_material(cdb, mat_path, out_root):
    """Reconstruct one material and write it as loose JSON under out_root/<mat_path>.
    Returns the output path, or None if the material isn't in the database."""
    mat = cdb.get_material(mat_path)
    if mat is None:
        return None
    out = os.path.join(out_root, mat_path.replace('/', os.sep).replace('\\', os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(mat, f, indent=2)
    return out


def _cli(argv):
    if len(argv) < 3:
        print("Usage: python -m pyn.sf_cdb <materialsbeta.cdb> <material-path.mat | list.txt> "
              "[out_dir]\n"
              "  Extracts materials from the Starfield material database to loose .mat JSON.\n"
              "  Give a single Materials\\...\\X.mat path, or a .txt with one path per line.")
        return 1
    cdb_path, target = argv[1], argv[2]
    out_root = argv[3] if len(argv) > 3 else os.getcwd()

    if target.lower().endswith('.txt'):
        with open(target, encoding='utf-8-sig') as f:
            paths = [ln.strip() for ln in f if ln.strip()]
    else:
        paths = [target]

    cdb = load_cdb(cdb_path)
    print(f"cdb v{cdb.version} (build {cdb.build_version}): {len(cdb.resource_to_db)} materials")
    ok = miss = 0
    for p in paths:
        out = extract_material(cdb, p, out_root)
        if out:
            ok += 1
            if len(paths) <= 5:
                print(f"  wrote {out}")
        else:
            miss += 1
            print(f"  NOT FOUND: {p}")
    print(f"done: {ok} written, {miss} missing")
    return 0


if __name__ == '__main__':
    if '--debug' in sys.argv:
        _DEBUG = True
        sys.argv.remove('--debug')
    sys.exit(_cli(sys.argv))
