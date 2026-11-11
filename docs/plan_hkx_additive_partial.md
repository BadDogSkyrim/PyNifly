# Plan: HKX additive, partial and lossless animations (group A)

**Status 2026-11-02:** approved; steps 1–5 built and tested (PYN_BUILD 67, uncommitted).
Step 6 (in game) is yours. As built, differences from the text below:
- Compression has a third value, *Uncompressed* (interleaved), which is what #442's files
  import as. Each game writes its own exact format: FO4 writes lossless for either one
  (no FO4 interleaved sample to copy), and Skyrim writes interleaved for either one
  (hk_2010 has no lossless class).
- A vanilla partial file's binding order isn't sorted. Export writes keyed bones in
  skeleton order. The set is the same; order is the binding's business.

For review before building. Issues: #381 items 1, 5–7; #434; Skyrim auxbones.
Root motion and paired offsets are group C, in a plan of their own.

## What the spike found (2026-11-02)

Every FO4 and Skyrim LE animation was censused (vanilla assets, both games). Each was
checked for its compression class, `blendHint`, binding list and reference frame.

| | FO4 | Skyrim LE |
|---|---|---|
| Spline-compressed | 8,824 | 4,991 |
| **Lossless-compressed** | 983 (all 1st-person, plus paired/sync idles) | 0 |
| **Additive** | ~780: hint 2 `ADDITIVE` 688, hint 1 `ADDITIVE_DEPRECATED` 88 | 17 (hk_2010 has only `ADDITIVE` = 1) |
| **Partial** (binding lists a subset) | common: 2, 6, 27, 35, 46… of 95 bones | 157: tails, ears, antennae, face offsets, weapon adjust |
| Reference frame (root motion) | most files, often static | 12 (dragon flight) |

- **The "six block" first-person format is `hkaLosslessCompressedAnimation`, not
  quantized.** It's simple: raw floats and raw quaternions, split into static and dynamic
  arrays. Each track carries a type/offset code per component. For rotations that's a
  u16 `(offset<<2)|type`, with type 0 identity, 1 static, 2 dynamic. Translation and
  scale have one such code per axis (x, y, z, pad). Header: the hkaAnimation base, ten
  hkArrays, then `numFrames`. The reader and writer are each maybe 150 lines. No unknowns
  left except the order of the dynamic data (frame-major or component-major), which the
  first real file will settle.
- **Additive keys are deltas from the rest pose; frame 0 is identity.** This holds for both
  FO4 values (1 and 2) and for Skyrim. A normal animation's frame 0 sits 30–180° away.
  Whether FO4's 1 and 2 *compose* differently in game (parent-side or child-side
  multiply) isn't known. We keep the value we read, so a round trip is safe either way.
- **Partial animations are just a binding list.** Track *i* drives bone
  `transformTrackToBoneIndices[i]`. 1st-person tracks have empty names, so the binding
  plus the 1st-person skeleton is the only mapping.

### What the code does today
- Skyrim: additive and partial **import** work. Additive keys go in as pose deltas.
- FO4: `blendHint` isn't read, and the writer always writes 0. Additive animations import
  as if they were absolute.
- Lossless can't be read at all: about 1,000 FO4 files fail.
- **Additive is a property of the armature** (`PYN_HKX_ADDITIVE`), set on import. Once
  one additive animation has been imported, every later export from that armature is
  written additive. That's a bug.
- **Export always writes every bone** of the skeleton. Partial animations come out full,
  and a bone the action doesn't key picks up whatever pose it has in the scene (#434).

## Blender representation (the part to agree on)

### 1. HKX settings live on the action, not the armature
An armature holds many actions, and additive, partial and compression are facts about one
animation. Each action gets a small property group, `action.pyn_hkx`:

| Property | Values | Import sets it from | Export |
|---|---|---|---|
| `blend` | Normal / Additive | `blendHint` (FO4 1 or 2 shows as Additive) | writes `blendHint` |
| `blend_hint_raw` | int, hidden | the exact value | FO4: writes it back as read, so a 1 stays 1. New additive: FO4 2, Skyrim 1 |
| `tracks` | All bones / Keyed bones | Keyed bones when the binding is partial | see 3 |
| `compression` | Spline / Lossless | the file's class | writes that class |

They're shown in a **PyNifly HKX panel in the Action editor sidebar**, and the export
dialog takes its defaults from the active action. The old armature property is read once,
as a fallback for an action that has no settings yet (compatibility back to 30.2.0 only),
and is no longer written.

### 2. Additive actions hold the delta as the pose
This is what Skyrim import already does. An additive action played on its own shows the
motion relative to the rest pose: a recoil kicks, then settles back to rest. To preview
it **on top of** a base animation, the way the game plays it, put the additive action in
an NLA strip set to **Combine**. Blender then multiplies rotations, adds locations and
multiplies scale, which is the same layering. Import does nothing to set that up; it's
your choice per scene. No baking, nothing lossy: export writes the pose values back as
deltas.

*Not chosen:* baking the additive onto a base pose at import. That needs a base we don't
have, and it can't be undone on export.

### 3. Which bones get tracks
- **All bones** (the default for full-body animations): export writes every skeleton bone,
  as now. *Change, for #434:* while sampling, a bone the action doesn't key has its pose
  values reset to rest first. Constraints such as IK still drive it, but a pose left over
  from another action no longer leaks in.
- **Keyed bones** (set by import for a partial file; you can switch it): export writes a
  track only for bones that have F-curves in the action, plus any bone driven by a
  constraint. It writes the binding list to match. This is how a tail, ear or weapon-add
  animation comes out partial again. It's also the answer if you want to author a new
  auxbones animation by hand: key only the tail bones and set Keyed bones.

### 4. Lossless compression
Import reads it, which opens all FO4 1st-person animations. Export writes lossless when the
action says Lossless. That covers #381 item 1 ("uncompressed for precision"): lossless
*is* exact. Spline stays the default for new actions. The spline tolerance and 48-bit
quaternion options (#381 item 2) belong in group C's compression options, not here.

### 5. First-person animations
They need the 1st-person skeleton as the reference
(`_1stPerson\...\skeleton.hkx`), the same as any other HKX import with a reference.
Nothing new to represent.

## Build order (each step test-first, on vanilla files)
1. Action property group, panel, and the armature-flag fallback. Export reads settings
   from the action. Test: import an additive animation, then a normal one onto the same
   armature; export the normal one and check it isn't additive.
2. FO4 `blendHint` read and write, raw value kept. Tests: round-trip `WPNFireAutoAdditive`
   (hint 2, 13 tracks) and `CameraHit01` (hint 1, 2 tracks); hint and track list preserved.
3. Keyed-bones export plus the binding list. Tests: Skyrim `dog_idle_spice_tail1`
   (3 tracks) round-trips as 3 tracks; FO4 `WPNFireAutoAdditive` as 13. #434: a stray
   pose on an unkeyed bone doesn't reach the file.
4. Lossless reader (FO4). Test: `44Pistol\WPNIdleReady` and `WPNPitchDownReadyAdd`
   decode; frame values continuous; rotations normalised.
5. Lossless writer. Test: a lossless round trip within float precision; the class and
   hint preserved.
6. In game, run by you: an FO4 1st-person pistol idle and its add exported from Blender,
   and a Skyrim tail animation authored with Keyed bones.

Not in this plan: interleaved-uncompressed (#442). It isn't in vanilla FO4 or Skyrim LE
(the census found none), and the BS/OS fix is for some modded files. It can join step 4's
reader as another class if you want it; it's small.

[Let's do this. I don't know what creature files they're dealing with but if it's an easy fix let's be good citizens.]

## Questions for you
1. Settings on the action, edited in an Action-editor panel: OK? -Yes
2. Additive = deltas as pose, preview with an NLA Combine strip: OK? -Yes, this is good
3. Keyed bones: does "F-curves or a constraint" match what you'd expect? And should
   *Additive* imply Keyed bones by default (vanilla adds are mostly partial)?
  - Yes, this is fine. Note that if a user wants a track to fix a bone in place they can just put a beginning and end key for the bone and they'll get what they expect. 
  - "Additive" should be independent of "keyed". The user should say what they want.
4. Include #442 (interleaved) in step 4, or leave it? -Include
