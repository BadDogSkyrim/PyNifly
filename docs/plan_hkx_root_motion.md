# Plan: HKX root motion, paired offsets, compression options (group C)

**Status 2026-11-02:** approved, and steps 1–5 are built and tested (PYN_BUILD 68,
uncommitted). Step 6 (in game) is yours. As built, differences from the text below:
- **A fourth action setting, *Root motion*,** says where Root's motion goes on export:
  - *Game default*: FO4 extracts it to the reference frame; Skyrim keeps it in Root,
    since Skyrim's motion is in the behaviour project.
  - *Reference frame*: extract. Import sets this for a Skyrim file that has one (the
    dragons).
  - *Root bone*: keep it in Root.
- **Root motion with no Root to put it on is kept on the action and written back.** Seventeen
  FO4 additive weapon animations (`WPNFireSingleAdditive` and others) carry samples but
  have no Root track. So does any armature without a Root bone.
- **Folding the convention was checked on vanilla:** in every turning run-start, the
  direction of travel matches the turn sample (L90 ends at +π/2).
- **Forty files start with a non-zero sample** (bloatfly evades and others). A round trip
  keeps the skeleton exactly where it was, but the reference frame then starts at zero.
- **The Skyrim reference frame** is at +0x34 (LE) or +0x38 (SE) in a 0x40 / 0x50 object.
  hkxcmd reads our LE output; our SE object is byte-identical to the one
  HavokBehaviorPostProcess makes from it.

For review before building. Issues: #381 items 2–4. (#239's Skyrim chair turn is driven by
the behaviour project, not the HKX, so this doesn't touch it.)
Group A (additive, partial, lossless) is done: see `plan_hkx_additive_partial.md`.

## What the spike found (2026-11-02, every FO4 vanilla actor animation)

### Root motion: `hkaDefaultAnimatedReferenceFrame`
- One sample per frame, `(x, y, z, w)`: the actor's travel from frame 0 in game units, and
  `w` = its **turn about Z in radians**. `RunForward` travels 236 units in 0.63 s;
  `RifleIdleAltTurnAroundFull_01` ends at w = −2π. Up is (0,0,1), forward (0,1,0) in
  every file.
- **3,802 FO4 animations move or turn:** 2,565 move, 505 turn, 599 both, plus 133 of the
  paired ones. 5,447 carry a reference frame that's static.
- **The Root track is static** in all of them: Havok extracted the motion *out of* Root.
  So in game, Root plus the reference frame is where the actor is.
- **PyNifly today:** import ignores the reference frame, so a run plays on the spot.
  Export writes one all-zero sample per frame. **Every moving or turning animation loses
  its motion on a round trip.** That's data loss, not a missing feature.
- Skyrim keeps root motion in the behaviour project (animationdatasinglefile), not in the
  HKX, except for 12 dragon-flight files. Out of scope here, apart from those 12.

### Paired offsets: `hkSimpleLocalFrame` "SyncAnimOffset"
- 187 FO4 files, all paired (kill moves, Dogmeat, Brahmin, power-armour punches). A third
  root-level variant named `SyncAnimOffset`, holding one transform: where this actor
  stands relative to the pair's origin when the animation starts.
- **The offset is its own data, not a copy of Root.** Across all 187 files:
  - In 100, Root's frame-0 transform equals the offset; in
    `PairedKill1HMShortShank_Lead` both are (3.17, 1.21, 0).
  - In the other 87, Root sits at the origin, and the offset is 150–200 units along Y,
    turned 180°. Examples: `PairedKillH2HSlideTackle_Victim` and
    `PairedDogmeatBiteHumanStanding_HumanLead`.
  - So it can't be derived from the pose.
  - No offset has any tilt: all are translation plus yaw.
- PyNifly drops it on import and doesn't write it on export, so the game has no offset
  for an exported paired animation.

### Compression options (#381 item 2)
- Our spline writer puts a control point on **every frame**, with degree 1, so it doesn't
  fit at all. A "rotation tolerance" option would do nothing. The only loss is
  quantisation: rotations are written **40-bit**. The writer already has 48-bit.
- Vanilla isn't per-frame: Havok's exporter reduces to a tolerance. Sampled 150 files
  each: FO4 channels are 74% linear, with a median of 0.87 control points per frame. Skyrim
  LE channels are 78% cubic, with a median of 0.41. Only 4% of Skyrim channels have one
  per frame. Our files come out 1.45× (FO4) and 1.9× (Skyrim) the size of vanilla's.
  Rotations: Skyrim is all 40-bit; FO4 is 97% 40-bit and 3% 48-bit.
- The "weapon jitter" complaint is a 40-bit precision problem. Lossless (group A) is the
  exact answer for FO4; 48-bit is the cheaper one.

## Blender representation (the part to agree on)

### 1. Root motion goes on the Root bone
Import adds the reference frame to the Root bone's own track: Root(t) = motion(t) ∘
Root(0). A run then runs across the scene and a turn turns, so you see what the game
does. Export reverses it: motion(t) = Root's travel and Z-turn since frame 0, written as
the reference frame, and Root's track written back static. This is exactly what Havok's
own exporter does (it extracts the motion from Root), and it's how Shiagur's rig works
(#381). The round trip is exact.

- **Which parts count as motion:** translation x, y, z and the turn about Z. Any other
  rotation Root has (tilt or roll) stays in the Root track, unextracted, as vanilla has it.
- **Vertical motion is extracted too, as vanilla does.** Of 9,261 FO4 reference frames, 47
  move vertically. All 47 are real level changes:
  - climbing into a vertibird (124–174 units),
  - deathclaw wall climbs and ambushes,
  - bloatflies dropping off the ceiling.
  Walk bob and crouches stay below Root, in the pelvis. **Rule for rigs:** Root carries
  only where the whole actor goes. Anything that bobs belongs on the pelvis or COM bone,
  or the game moves the whole actor (its collision capsule) up and down with it.
- **Import must survive bad vanilla data:** three `Stand_to_Run_L180` files have Z values
  in the millions. Import warns and drops the reference frame of any sample past a sane
  bound (say 100,000 units) rather than flinging the armature off-screen.
- **An action that doesn't move Root** exports a reference frame of zero samples, one per
  frame, as now. Vanilla always has one sample per frame, even when nothing moves.
- *Not chosen:* animating the armature **object**. That previews just as well, but the
  armature object's transform already means things to nif export (skinning, placement),
  and object motion lives outside the pose, where NLA and partial actions don't see it.

### 2. Paired offset is an Empty, child of the armature (Bad Dog, 2026-11-02)
The marker *is* the setting: move the Empty and you've changed the offset.
- **One Empty per paired action**, parented to the armature and named
  `SyncAnimOffset:<action>`. Its location is the offset's translation; its Z rotation is
  the yaw. It's drawn as a 5 m cone (Bad Dog, 2026-11-03; was 20-unit Arrows).
- **The action points to its Empty** (`action.pyn_hkx.sync_offset`, an object pointer).
  The offset belongs to one animation, but an armature can hold many paired actions,
  each with its own offset. The pointer is what ties them together. No pointer means no
  offset, and export writes none.
- **Import** creates the Empty from SyncAnimOffset and sets the pointer.
- **Export** writes the Empty's transform relative to the armature, as the
  hkSimpleLocalFrame and the `SyncAnimOffset` root variant. Only translation and Z
  rotation are written; vanilla has no tilt.
- **The HKX panel** shows the pointer, with an **Add sync offset** button for a new paired
  action. That button adds the Empty at the armature origin and points the action to it.
- **Nif export must skip these Empties**, or they'd come out as NiNodes. They're tagged
  with a custom property and skipped.
- *Not chosen:* animating the Empty from the same action, using Blender's slotted actions.
  It's neat, but switching the armature's action wouldn't switch the Empty's.

### 3. Rotation precision is an action setting
Compression *Spline* gains a **Rotation bits: 40 / 48** setting. 40 is the default (what
export writes today; step 4 censuses what vanilla uses). Import records what the file
used, so a round trip keeps it.
Lossless/Uncompressed are unchanged.

## Build order (each step test-first, vanilla files)
1. FO4 reference-frame read and write. Test: `RunForward` (moves) and
   `RifleIdleAltTurnAroundFull_01` (turns 2π) round-trip their samples at the pyn level.
2. Root-motion import onto Root. Export extracts it again. Tests: after importing
   RunForward, Root sits 236 units forward on the last frame; export gives back the same
   samples and a static Root track. The turn file comes back at −2π. An action that
   doesn't move Root writes a static frame.
3. Sync offset: read and write, the Empty and the action's pointer to it, and the panel
   button. Tests:
   - `PairedKill1HMShortShank_Lead` (offset equals Root) and `PairedKillH2HSlideTackle_Victim`
     (offset separate) round-trip their offsets.
   - Moving the Empty changes the exported offset.
   - Nif export of the armature writes no node for the Empty.
4. Rotation bits: record on import and write 48-bit when set. Test: a 48-bit spline round
   trip is more accurate than 40-bit on the same data.
5. Skyrim dragon reference frames (12 files): the same read and write in the hk_2010
   writer, if the layout matches. Spike first; drop it if it's different.
6. In game, run by you: an exported RunForward runs (doesn't skate), a turn turns, and a
   paired kill lines up.

## Questions for you
1. Root motion on the Root bone (not the armature object): OK? -Yes
2. Settled by the census: extract x, y, z and the Z-turn, as vanilla does.
3. Sync offset: settled. It's an Empty that is a child of the armature, and the action
   points to it. (The question left open is in "Still open" below.)
4. Rotation bits per action, default 40: OK? Or should FO4 just always write 48? -Record on import, use on export. user can change the value if desired.
5. Skyrim dragons (step 5): worth it, or skip? -worth it

## Still open
- **Several paired actions on one armature means several Empties.**
  - Option A: show them all.
  - Option B: show only the active action's Empty. A small handler would hide the others
    when you switch actions.
  - I'd start with A and add B only if the clutter bothers you. - This is fine. 
