# Plan: Skinned tree NIF import (BSTreeNode + LOD + dup'd partitions)

Status: **investigation** — capturing what we know before committing to changes.

## The problem reports

Working from `tests/tests/SkyrimSE/treeaspen03.nif` (vanilla SE) as the
authoritative test case. (We were originally looking at
`BSKTreeAspenGreen01.nif`, a Bad Dog Furry mod asset, but it has a
file-specific anomaly — see "Setting aside" below.)

Two user-visible problems on import:

1. Several NIF block types come through without their type-specific
   data preserved. On round-trip the file would lose LOD selection
   state, multibound culling info, and the tree-bone references.
2. Bones and partitions visibly repeat: shape `:7` from
   `treeaspen03.nif` lands in Blender as a mesh with **13 vertex
   groups** — 4 unique skinning bones × 3 partition copies + 1 SBP
   marker. Two armatures appear, one per skinned shape.

## The test files

`treeaspen03.nif` block hierarchy (vanilla, what we want to make work):

```
BSTreeNode TreeAspen03.nif                ← root; adds Bones1[]/Bones2[]
  BSXFlags
  BSMultiBoundNode FadeNode Anim          ← adds MultiBound ref + CullingMode
    NiSwitchNode TreeAspen03              ← adds SwitchFlags + ActiveIndex
      NiNode (LOD0 container)
        NiSwitchNode :5                   ← inner LOD switch
          NiNode :6
            NiNode TrunkBone              ← skeleton root
              NiNode BranchBoughBone01/02
                NiNode BranchBone01/02
            BSTriShape :7 (skinned trunk+branches)   ← prop=v395/t273  bones=13(5 uniq)
            BSTriShape :15 (skinned trunk only)      ← prop=v304/t300  bones=5(5 uniq)
        NiNode (LOD1 container)
          BSTriShape TreeAspen03_1:0  (leaf cards, LOD1)
          BSTriShape TreeAspen03_1:1
      NiNode (LOD2 container)
        NiTriShape TreeAspen03_1:0  (leaf cards, LOD2, *Ni*TriShape)
        NiTriShape TreeAspen03_1:1
  bhkCapsuleShape (trunk collision)
```

Important normality checks from a vanilla-tree survey (~80 NIFs scanned):

- **DUP-BONES is universal in vanilla skinned trees.** Every
  `treeaspen*.nif` / `treepine*.nif` / similar shows 3 SkinPartitions
  with the same partition palette repeated. This is the format, not
  a corruption.
- **0-tri BSTriShape is NOT universal.** Only `BSKTreeAspenGreen01.nif`
  has it. All vanilla trees have proper `triangleCount` on the
  BSTriShape header.

## Setting aside: the BSKTreeAspenGreen01 0-tri anomaly

`BSKTreeAspenGreen01.nif` reports `prop=v729/t0  read=v729/t0` on the
skinned shapes: BSTriShape's header says zero verts and zero triangles,
yet `NiSkinPartition.partitions[i].vertex_data` contains 729 verts
(nifly aggregates this), and the partition tri arrays presumably contain
the actual triangles (not yet aggregated by nifly). NifSkope shows
v0/t0 because it reads the header.

This pattern doesn't appear in any vanilla tree. We are **explicitly
deferring** that file. Document open question:

> Does the engine actually render that file? If so, partition triangles
> must be a legal storage location. If not, the file is just malformed.
> Hugh has not committed to fixing it.

## What we observe at each layer

### nifly layer (C++ from upstream)

We do not have the nifly submodule checked out locally
(`NiflyDLL/external/nifly` is empty). The functions of interest used
in `NiflyWrapper.cpp`:

| Function | What it appears to do (inferred) |
|---|---|
| `nif->GetShapeBoneList(shape, names)` | Returns a vector<string> of bone names. Treeaspen03 :7 returns 13 entries with duplicates → **almost certainly the concatenation of the per-partition bone palettes**, not the master skin-instance bone list. |
| `shape->GetNumVertices()` | Returns sum across partition vertex_data arrays when BSTriShape header is empty (BSKTreeAspen01 case) — gives 729. |
| `shape->GetNumTriangles()` | Returns the BSTriShape header value only — gives 0 for BSKTreeAspen01. Does *not* aggregate partition tris. |
| `nifly.getShapeBoneWeights(shape, bone_id=N, …)` | Returns weights for the Nth entry in whatever list `GetShapeBoneList` is returning. **Unverified whether the indexing is partition-local or skin-instance-global.** |

### pyn layer (`io_scene_nifly/pyn/pynifly.py`)

```python
@property
def bone_names(self):
    # calls getShapeBoneNames → 13 entries with dups for treeaspen03 :7
    ...
    return self._bone_names

@property
def bone_weights(self):
    """Dictionary of bone weights {bone-name: [(vertex-index, weight), ...]}"""
    if self._weights is None:
        self._weights = {}
        for bone_idx, name in enumerate(self.bone_names):
            self._weights[name] = self._bone_weights(bone_idx)   # ← overwrites duplicates
    return self._weights
```

**Bug:** because the dict is keyed by name and `bone_names` has duplicates,
the last-iterated copy of each bone's weights overwrites the first two.
We lose 2/3 of any bone's weights for a 3-partition shape *if* the
weights returned per partition are genuinely different per partition.

### Blender import layer (`io_scene_nifly/nif/import_nif.py`)

```python
def mesh_create_bone_groups(self, the_shape, the_object):
    vg = the_object.vertex_groups
    for bone_name in the_shape.bone_names:        # iterates 13 entries
        new_vg = vg.new(name=self.blender_name(bone_name))   # Blender auto-suffixes dups
        for v, w in the_shape.bone_weights[bone_name]:
            new_vg.add((v,), w, 'ADD')
```

Blender auto-suffixes duplicate names → `TrunkBone`, `TrunkBone.001`,
`TrunkBone.002`. All three end up containing the same (overwritten)
weights from `bone_weights[bone_name]`.

```python
def mesh_create_partition_groups(the_shape, the_object):
    for p in the_shape.partitions:
        if p.name in vg:
            new_vg = vg[p.name]      # ← dedups partition vertex groups by name
        else:
            new_vg = vg.new(name=p.name)
        ...
```

Partitions are *already* deduped by name on import. Three `SBP_32_BODY`
partitions become one vertex group — but the partition-tri mapping
distributes triangles correctly. **Partition side appears OK.**

### Export layer (`io_scene_nifly/nif/export_nif.py`)

```python
new_shape.setShapeWeights(nifname, bone_weights)
```

Export sends `(bone_name, [(v, w), ...])` pairs to nifly. nifly rebuilds
the NiSkinInstance + NiSkinData + NiSkinPartition from scratch and
batches into partitions itself. **Export already deduplicates** by
nature of being driven by Blender's one-vertex-group-per-bone layout.

## Required block-type extras (issue 1)

Per nif.xml (`C:\Modding\Tools\NifSkope\nif.xml`):

| Block | Fields beyond NiNode |
|---|---|
| `NiSwitchNode` | `Switch Flags` (byte), `Index` (uint) — currently lost |
| `BSMultiBoundNode` | `Multi Bound` (Ref → BSMultiBound), `Culling Mode` (uint enum, FO3+) — currently lost |
| `BSMultiBound` | `Data` (Ref → BSMultiBoundData) — child block we don't wrap |
| `BSMultiBoundOBB` | `Center` (Vec3), `Size` (Vec3), `Rotation` (Matrix33) — child block we don't wrap |
| `BSTreeNode` | `Num Bones1` + `Bones1[]` (Ptr<NiNode>), `Num Bones2` + `Bones2[]` (Ptr<NiNode>) — currently lost |

Hugh's directives for these:

- NiSwitchNode → its own buffer struct (`NiSwitchNodeBuf`) following
  existing subclass pattern (e.g. `BSValueNodeBuf`).
- BSMultiBoundOBB → represent in Blender as a mesh primitive cube:
  `location = center`, `dimensions = size`, `rotation = rotation`.
  The MultiBound + OBB blocks roundtrip via that mesh.
- BSTreeNode → capture Bones1/Bones2 lists. Hugh doesn't fully
  understand their semantics yet ("If I understood better how those
  are used we might be smarter but I don't"). Round-trip first,
  optimize later.

## Bone/partition consolidation (issue 2)

Hugh's directives:

- One vertex group per unique bone in Blender; weights summed across
  partition copies.
- Partitions: collapse identical-name copies (already happens by
  accident in import; we should make it deliberate).
- On export, the rebuilt partition structure must not re-duplicate.
  This already works correctly since export is driven by Blender
  vertex groups.
- **Single armature** for the whole nif, not one per skinned shape.

## Known unknowns (must resolve before changing code)

1. **What does `nifly::NifFile::GetShapeBoneList` actually return?**
   The skin instance's master bone list (= 4 unique for `:7`), or the
   concatenated partition palettes (= 12 for `:7`)? We observe 12, but
   we don't know which of:
   - upstream nifly designed it this way, vs.
   - our `getShapeBoneNames` is iterating partitions instead of skin
     instance.

   Need to inspect the C++ source. The submodule isn't checked out;
   could grab a copy from upstream
   (`https://github.com/SK83RJOSH/nifly`) or look at
   `NiflyDLL/x64/Release/io_scene_nifly/scripts/` artifacts that may
   reference it.

2. **What does `nifly.getShapeBoneWeights(shape, bone_idx, …)` index
   into?** If `bone_idx=0` and `bone_idx=4` both refer to TrunkBone
   from different partitions, do they return the same data
   (deduplicated) or different (partition-local) data? Determines
   whether `_weights[name] = ...` is overwriting equivalent data or
   genuinely losing weights.

3. **How are the partitions of `:7` actually different?** All three
   have name=`SBP_32_BODY`, part_id=None, flags=1. If they all carry
   the same bone palette and the same logical content, why does the
   file split into three? Hypothesis: each is a GPU-batchable subset
   of triangles to keep per-batch state small. The split is purely
   for hardware skinning.

4. **What is `BSTreeNode.Bones1[]` / `Bones2[]` for?** Best guess from
   the NIF wiki: two LOD groups, each listing the bones used at that
   LOD. The skinned shapes' bones live in Bones1 (high-detail) while
   Bones2 might be empty or reference a simpler skeleton. Need a
   couple of vanilla examples to confirm.

5. **Two armatures vs one** — is there an existing scheme for
   consolidating armatures per file, or are we creating per-shape
   armatures unconditionally? Look at `import_nif.py`'s armature
   creation path.

## Phased plan

Each phase is **TDD: one failing test first, then the fix.**

### Phase 0 — Verify the diagnosis ✅ DONE (2026-05-30)

nifly source read at `C:\Modding\Nifly\` (NOT the empty `external/nifly`
submodule). Findings (probe: `c:\tmp\probe_bonelist.py`):

- **nifly is faithful.** `GetShapeBoneList` (`src/NifFile.cpp`) reads
  `skinInst->boneRefs` directly and concatenates nothing. The 13 entries are
  literally what the file's `NiSkinInstance` stores.
- **The file's bone list is partition-palette-aligned.** For `:7` (id 18):
  `boneRefs` node ids = `[7,14,15,16,17, 7,16,17, 7,14,15,16,17]` — the three
  SkinPartitions' palettes (5 + 3 + 5 = 13), only **5 unique** nodes.
- **The 13 positions carry DISJOINT vertex sets (overlap = 0).**
  `GetShapeBoneWeights(boneIndex)` matches `vertex.weightBones[i] == boneIndex`,
  so each position is its own vertex set. TrunkBone spans positions 0/5/8 =
  142 + 10 + 239 = **391 distinct verts**.
- **pyn loses data.** `_weights[name] = getShapeBoneWeights(idx)` is keyed by
  name → only the last position survives. TrunkBone: **391 → 239**, 152 verts
  dropped. Same for every repeated bone.

**Resolution: this is a pure pyn-layer fix, no DLL change.** Aggregate by bone
(sum weights per vertex across all same-bone positions); return unique
`bone_names`. Export is driven by Blender vertex groups, so nifly rebuilds the
partition palettes itself — the 13-way split need not be reproduced.

- [x] Read `GetShapeBoneList` / `GetShapeBoneWeights` source.
- [x] Compared per-position weight sets for shared bones: **different** vertex
      sets per position (disjoint), so overwrite loses data → fix is sum/union.
- [ ] Confirm partition-tri mapping works (deferred to Phase 1 test).

### Phase 1 — Bone dedup + weight aggregation (pyn layer)
- [ ] Change `bone_names` to return uniques (or add `unique_bone_names`).
- [ ] Change `bone_weights` to aggregate across partition copies into
      the single bone entry.
- [ ] Existing callers (`mesh_create_bone_groups`,
      `add_bones_to_arma`, etc.) become correct automatically.

### Phase 2 — Single armature per file
- [ ] Locate the armature-creation logic.
- [ ] Make it idempotent across shapes — first skinned shape creates
      the armature, subsequent shapes attach to it.

### Phase 3 — NiSwitchNode preservation
- [ ] New `NiSwitchNodeBuf` struct (C++ + Python), fields
      `switchFlags` (uint8) and `activeIndex` (uint32). Modeled on
      `BSValueNodeBuf`.
- [ ] Add C++ getter/creator (`getNiSwitchNodeProps`,
      `addNiSwitchNode`). Route through the buffer-type dispatch
      tables.
- [ ] Capture as custom props on the Empty (`pynSwitchFlags`,
      `pynSwitchActiveIndex`) on import; restore on export.

### Phase 4 — BSMultiBound{Node,OBB} preservation
- [ ] `BSMultiBoundNodeBuf` adds `cullingMode` (uint32) + `multiBoundID`
      (uint32 ref).
- [ ] New `BSMultiBoundBuf` (data ref) and `BSMultiBoundOBBBuf`
      (center Vec3, size Vec3, rotation 3×3 floats).
- [ ] Import: create a mesh-cube child of the MultiBoundNode Empty;
      `location = center`, `dimensions = 2 × size` (OBB half-extents),
      `rotation = decomposed Matrix33`. Mark with a custom prop so
      export recognises it.
- [ ] Export: find the OBB-marker mesh, decompose its transform,
      write back. If no OBB mesh exists (user deleted it), emit
      a sensible default or skip the MultiBound.

### Phase 5 — BSTreeNode preservation
- [ ] `BSTreeNodeBuf` adds `numBones1` + `numBones2` + ID arrays.
      Variable-length so likely uses a separate getter/setter rather
      than fixed fields in the buffer.
- [ ] Import: store as `pynBSTreeBones1` and `pynBSTreeBones2` custom
      props on the root Empty (list of bone names, similar to
      `PYN_HKX_BONES`).
- [ ] Export: look up bones by name, write back the Ptr arrays.

### Phase 6 — Round-trip test
- [ ] One Blender test `TEST_VANILLA_TREEASPEN_ROUNDTRIP`:
  - Import `tests/SkyrimSE/treeaspen03.nif`
  - Assert one vertex group per unique bone (5 for `:7`)
  - Assert single armature with all bones
  - Assert `pynBlockName` survives on NiSwitchNode / BSMultiBoundNode / BSTreeNode
  - Assert switch/multibound/treenode extras survive on import then export
  - Re-import the export, check structural equivalence (bone counts,
    triangle counts, multibound OBB roughly preserved)

## Risks

- The NiSkinPartition data layout for old-format Skyrim files
  (BSKTreeAspen01) and even some vanilla skinned-tree files is
  poorly documented. We may introduce regressions in unrelated
  skinned meshes if we tweak `bone_names` aggressively.
- Two armatures per tree is the long-standing behavior; consolidation
  may affect existing user workflows.
- BSTreeNode.Bones1/Bones2 are written but we don't understand what
  the engine does with them. Wrong values could cause silent issues
  in-game.

## Test-first checkpoints before any code change

1. Phase 0 investigation results recorded in this doc.
2. Failing test added that demonstrates each bug *concretely* with
   numeric expectations, run before the fix.

## Open questions for Hugh

1. Are you OK with one combined test or do you want separate tests
   per phase? You said "one test if possible". Confirming.
2. For BSTreeNode Bones1/Bones2 — if we can't figure out semantics,
   is "round-trip the exact names verbatim" acceptable, or do you
   want me to dig more first?
3. Two armatures consolidation — if existing user workflows depend
   on per-shape armatures (unlikely but possible), should I gate this
   behind a setting?
