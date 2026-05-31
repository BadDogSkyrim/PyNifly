# Mini-plan: Skinned-tree import/round-trip

Execution plan distilled from the investigation in
[`plan_skinned_tree_import.md`](plan_skinned_tree_import.md) (which holds the
detail, observations, and open questions). This file is the actionable sequence.

**Goal:** vanilla skinned trees (`tests/SkyrimSE/treeaspen03.nif`) import clean
and round-trip. Two defects:

- **(A) Duplication** — `:7` lands as 13 vertex groups (5 unique bones × 3
  partition copies + marker); the file makes 2 armatures instead of 1.
- **(B) Dropped block extras** — `NiSwitchNode`, `BSMultiBoundNode` /
  `BSMultiBound` / `BSMultiBoundOBB`, and `BSTreeNode` lose their type-specific
  data on import → can't round-trip.

The DLL updates are all in **(B)**. **(A)** is likely pure-Python — but Phase 0
settles that.

## The DLL extension recipe (one pattern, reused per block)

Model on **`BSValueNode`** (fixed-field node) and **`BSBoneLODExtraData`** (node
+ variable-length array). For each new block:

1. **`nifdefs.py`** — new `XxxBuf(pynStructure)` mirroring `NiNodeBuf`'s base
   fields + the extras; add `XxxBufType` to `PynBufferTypes` (next free = **73**,
   then 74, 75…).
2. **`NiflyWrapper.cpp`** — `getXxx(nifref, id, buf)` + `addXxx(f, name, buf,
   parent)`, then wire both into the dispatch tables by **appending at the
   matching index**: `getterFunctions[]` (~L6403) and `setterFunctions[]`
   (~L6499). Variable-length arrays get an extra Len+Data getter/setter modeled
   on `getBoneLODInfo` (L3196).
3. **`niflydll.py`** — declare the new function signatures.
4. **`pynifly.py`** — wrapper class exposing the fields.
5. **`import_nif.py` / `export_nif.py`** — stash/restore as custom props (or a
   mesh-cube for the OBB).
6. **Rebuild Debug DLL** (Claude), verify version.

## Per-block specifics

| Block | New BufType | Fields / representation |
|---|---|---|
| `NiSwitchNode` | 73 | `switchFlags` (u8), `activeIndex` (u32) → custom props `pynSwitchFlags`, `pynSwitchActiveIndex` on the Empty |
| `BSMultiBoundNode` | 74 | adds `cullingMode` (u32) + `multiBoundID` (u32 ref) to the node buf |
| `BSMultiBound` + `BSMultiBoundOBB` | 75 (+ child) | `center` Vec3, `size` Vec3, `rotation` 3×3 → imported as a **mesh-cube** child (`location=center`, `dimensions=2×size`, `rotation=Matrix33`), marker prop for export |
| `BSTreeNode` | 76 | `numBones1`+`Bones1[]`, `numBones2`+`Bones2[]` (Ptr→NiNode) — **variable-length**, so fixed buf + `getBSTreeBones`/`setBSTreeBones` Len+Data pair; stash as `pynBSTreeBones1/2` name lists. Round-trip verbatim (semantics unknown — acceptable). |

`NiSwitchNode` takes two children, usually or always NiNodes that group the children of interest. The TriShapes under the first child are always skinned; under the second child are never skinned. They represent the same objec but need not be and usually are not identical. On import we must represent this hierarchy. On export we must discover and re-create it. Blender children aren't ordered (I think)--we can find the branch that has the skinned meshes and make sure they go first.

`BSTreeNode` `Bones 1` seems to point to the root of the armature and looks like there's always only one (we should check this). `Bones` seems like just a list of the rest of the bones.

## Phase order (TDD — failing test first each phase)

- **Phase 0 — settle the bone-list question (gates A).** Does
  `GetShapeBoneList` return the **skin-instance master list** (unique) or
  **concatenated partition palettes** (the 13)? Either pull the nifly submodule
  (`NiflyDLL/external/nifly` is empty) to read the source, or probe empirically
  with `inspect_aspen_blender.py`. Outcome decides: pure-Python dedup vs. a new
  DLL getter for the master bone list. **No code until this is recorded in the
  investigation doc and checked with Hugh.** 
- **Phase 1 — bone dedup + weight aggregation** ✅ DONE (pyn + Blender importer,
  no DLL). Phase 0 proved nifly is faithful: the file's NiSkinInstance stores a
  partition-palette-aligned 13-entry bone list (5 unique nodes), each palette
  position carrying a disjoint vertex set; pyn's name-keyed overwrite dropped
  all but the last (TrunkBone 391→239).
  - `pynifly.py`: added `unique_bone_names` (dedup **by node id**,
    first-occurrence order) and rewrote `bone_weights` to aggregate **by node
    id** (sum weights per vertex across positions), keyed by first-occurrence
    name. `bone_names`/`bone_ids` left raw.
  - `import_nif.py`: `mesh_create_bone_groups` and the bind-xform check now
    iterate `unique_bone_names` (was raw `bone_names`, which made
    `TrunkBone`/`.001`/`.002`). `get_used_bones()` was already correct (keys off
    `bone_weights`).
  - Tests: `TEST_TREE_BONE_AGGREGATION` (pyn), `TEST_TREE_SKINNED_BONES`
    (Blender — `:7` → 5 vgroups, no dupes). Full pyn+anim green; Blender suite
    green (224) for pyn change; re-run after importer change.
- **Phase 2 — single armature per file** ✅ ALREADY SATISFIED (verified
  2026-05-30). treeaspen03 imports with ONE armature
  (`TreeAspen03.nif:ARMATURE`); both skinned shapes (`:7` and `:15`) bind to it
  via armature modifier, 5 bone vgroups each. The "two armatures" note in the
  investigation doc was stale (older state / BSKTreeAspenGreen01). No code
  needed; revisit only if a multi-shape file shows per-shape armatures.
- **Phase 2.5 — fix `getNodeChildren` to return the real ordered Children
  array.** Current impl uses `GetChildRefs(std::set&)`, which aggregates
  *everything* under the node (children + effects + collision + extradata +
  multibound/bones refs), loses NIF order (set is pointer-sorted), and counts
  null slots — e.g. it returns `[-1,-1,4,37]` for the outer switch. nifly's
  `NiNode::childRefs` is a public, already-ordered `NiBlockRefArray<NiAVObject>`
  (the actual Children property, separate from the rest), so the fix is a small
  wrapper-only change — **no deep nifly work**. `getNodeChildren` has **zero
  Python callers today** (importer uses `node.parent` + `collisionID` +
  `get_extra_data`), so redefining its semantics is regression-free.
  - **Decision (Hugh):** return only the **real** children (drop `NIF_NPOS`
    slots), in NIF order. If a future faithful round-trip needs the empty slots,
    fix it then.
  - Iterate `node->childRefs` via `GetSize()`/`GetBlockRef(i)`, skip `NIF_NPOS`,
    null-guard `GetBlock<NiNode>` (returns 0 for shapes → also fixes the crash).
  - Then expose order at the pyn level: `NiNode.children` (ordered child
    objects) and, on the `NiSwitchNode` wrapper, `child1`/`child2` +
    `skinned_child`/`unskinned_child` so users never intuit order.
  - Test: `getNodeChildren` on the two switches returns exactly `[4,37]` /
    `[6,31]`; no `-1`; shapes return 0 children without crashing.
- **Phase 3 — `NiSwitchNode`** ✅ switch-flags DONE (DLL recipe proven
  end-to-end). Added NiSwitchNodeBuf (switchFlags u16 + switchActiveIndex u32) to
  nifdefs.py + NiflyDefs.hpp (NiSwitchNodeBufType=73); getNiSwitchNode/
  addNiSwitchNode in NiflyWrapper.cpp wired into getter+creator tables (setter
  nullptr); NiSwitchNode pyn class exposes switch_flags/active_index. Import/
  export round-trip is AUTOMATIC via the generic extract→getbuf(values=obj) path
  (switchFlags stored as a custom prop when non-zero). Tests: TEST_NISWITCHNODE
  (pyn read+create round-trip), TEST_NISWITCHNODE_IMPORT (Blender props).
  treeaspen03: outer flags=3, inner flags=1, both active_index=0.
  **Still TODO for Phase 3:** the child1/child2 pyn API + the skinned-first/
  unskinned-second child-ordering on export (the invariant below). Not needed
  for round-tripping the flags; needed when we rebuild the switch hierarchy on
  export. Full Blender export round-trip deferred to Phase 6 (tree-mesh export
  currently errors on unweighted verts — separate issue).

## Import-naming oddities (surfaced by tree import, 2026-05-30)

- **Unnamed nodes/shapes → block name.** ✅ Fixed in `import_nif.py`: nameless
  nif blocks (the skinned-tree BSTriShapes `:7`/`:15` and the LOD-container
  NiNodes are nameless in vanilla) were importing as Blender's `Object.NNN`. Now
  use the block name as the base (`NiNode.NNN`, `BSTriShape.NNN`). The true nif
  name (possibly empty) is stored in `pynNodeName` (nodes already did; now shapes
  do too).
- **BSMultiBoundNode type in name? → NO.** Named nodes keep their name; type
  lives in the `pynBlockName` prop, consistent with every other node type. Don't
  special-case it. Revisit only if Phase 4's cube representation needs a marker.
- **NiTriShape names are NOT dropped.** The LOD2 NiTriShapes `.001` suffix is a
  legit Blender collision with the LOD1 BSTriShapes that share the same nif name
  (`TreeAspen03_1:0/:1`) — correct behavior, not a bug.
- **Round-trip TODO (Phase 6):** export derives nif names from `obj.name`
  (shapes: `unique_name`; nodes: `nonunique_name`), NOT `pynNodeName`. So a
  renamed unnamed block round-trips as its block name, not the original empty
  name. Current behavior already didn't preserve empty names; fixing it means
  making export prefer `pynNodeName` when present — do this in Phase 6 where
  round-trip is built and tested.

## NiSwitchNode invariant (validated on treeaspen03)

- A `NiSwitchNode` has **exactly 2 children**.
- **child[1]** (the second child) is not a skinned node and has **no skinned
  descendants**.
- child[0] is unconstrained (it may itself contain a nested switch, so it can
  hold both skinned and unskinned descendants — the outer switch in
  treeaspen03 is exactly this).
- If **neither** child has skinned descendants, either order is allowed — emit a
  **warning**.
- Switches can nest (treeaspen03 has outer LOD0/LOD2 split, inner skinned/LOD1
  split). The invariant holds per-switch.
- **Phase 4 — `BSMultiBound{Node,OBB}`** ✅ DONE. 3 buffer types (74/75/76):
  BSMultiBoundNodeBuf (cullingMode + multiBoundID ref), BSMultiBoundBuf (dataID
  ref), BSMultiBoundOBBBuf (center/size/rotation). C++ getters + creators (refs
  linked in the creators, not childRefs — referenced blocks ignore the parent
  arg). Import: OBB → wireframe cube child (matrix_local = center / 3x3 /
  half-extents; marked pynMultiBoundOBB, skipped as a shape on export). Export:
  `_export_multibound` rebuilds OBB+BSMultiBound from the cube and sets the
  node's multiBoundID. NOTE: build the OBB/BSMultiBound via `nifly.addBlock`
  directly, NOT `nif.add_block` — the latter wraps the new non-node block in a
  NiObject whose getNodeByID returns a dangling pointer (C++ exception). Tests:
  TEST_BSMULTIBOUND (pyn), TEST_BSMULTIBOUND_ROUNDTRIP (Blender). 229 green.
- **Phase 5 — `BSTreeNode`** ✅ DONE. Bones1/Bones2 are variable-length
  node-pointer arrays, so NO new buffer type — standalone `getBSTreeNodeBones`/
  `setBSTreeNodeBones(nif, id, which, ...)` Len+Data functions (declared
  `extern "C" NIFLY_API` in NiflyWrapper.hpp — required or ctypes can't find the
  symbol). Also added BSTreeNode to `SetNifVersionWrap` so a BSTreeNode root can
  be created. pyn BSTreeNode.bones1/bones2 (name lists), set_bone_ids(which,ids).
  Import stashes `pynBSTreeBones1/2` JSON name lists on the root Empty; export
  `_export_bstreenode_bones` (after bones are written) resolves names via
  findNodeByName and writes the pointer arrays. treeaspen03: Bones1=['TrunkBone']
  (armature root), Bones2 = the 4 branch bones — confirms Hugh's hypothesis.
  Tests: TEST_BSTREENODE (pyn), TEST_BSTREENODE_ROUNDTRIP (Blender).
- **Phase 6 — `TEST_VANILLA_TREEASPEN_ROUNDTRIP`** (one combined test): 5 vgs
  for `:7`, single armature, block-name + all extras survive
  import→export→re-import.

**Deferred:** `BSKTreeAspenGreen01.nif`'s 0-tri-header anomaly stays parked (no
vanilla tree has it; unknown if the engine even renders it).

## Before cutting code

- **Phase 0 is the real first move** and it's cheap (pull submodule + probe the
  bone list). It decides whether (A) touches the DLL at all.
- Reminder: Debug DLL is what Blender dev mode loads — rebuild + verify after
  each C++ change.
