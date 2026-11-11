# Starfield cloth: tails that hang down at rest

## Why

Some crowd tails never get physics. They show the cloth's own rest pose, which is straight
out behind. Tested in game on 2026-11-11:

| crowd skeleton tail bones | tail cloth | what the tail does |
|---|---|---|
| drooped | attached | sticks straight out |
| drooped | detached | **hangs, in the drooped pose** |

So the skeleton's tail pose works, but while a cloth is attached, the cloth holds the bones
at its own rest pose even when it isn't simulating. To make those tails hang, the cloth's
rest pose has to be the droop too.

The `.rig` file isn't involved: vanilla's `skeleton.rig` has no tail bones, and Extended
Skeleton ships no rig.

## What's already done

- **Crowd skeletons drooped.** `C_Tail_01`–`08` in all eight crowd skeleton nifs carry Bad
  Dog's pose: `human_crowd` (`HumanCrowdRace`, which the crowd NPCs use) and
  `FSFCanine_Crowd` (`FSFFoxCrowdRace`), each male and female, plain and facebones. They
  were patched in place, so the Vortex mod folders have the change too. Kit, originals and
  `restore_originals.py` are in `C:\tmp\crowd_tail_pose\`.
- **Tail variants restored.** All 26 crowd tail variants have their cloth back,
  byte-identical to before the test.
- **Player race not changed.** It uses Extended Skeleton's file, whose tail is still straight.

## The PyNifly change

**The trap:** a cloth's rest pose lives in two places in its block:

- the **cloth skeleton**: its own copy of the bones, with a reference pose;
- the **particle positions**: the sim pose.

On export, PyNifly takes the particle positions from the sim mesh. But for a cloth that came
in with a block, which is every exported tail, it keeps the cloth skeleton from the old block.
`model_from_pictures` in `nif/cloth_viz.py` rebuilds the skeleton from the armature only when
there's no block. Re-posing a tail in Blender therefore gives drooped particles on a straight
cloth skeleton. It's unclear which of the two the game uses for a tail that isn't simulating,
so both must droop.

**The change:** in `model_from_pictures`, when the cloth has a block and an armature is given,
take each cloth-skeleton bone that the armature also has and set its reference pose from the
armature's rest. Use the same conversion `_armature_bones` already does: metres, the nif
root's space. Keep the bone names, order and parents exactly as the block has them, because
everything else in the cloth refers to bones by index. Bones the armature lacks keep the
block's values. Log each bone that moved by more than a small tolerance, so an
unintended change is visible.

**Effects:**

- **Skin binds.** The particles' skin binds are rebuilt from the skeleton, and
  `bind_matrices` already composes them from the reference pose, so they follow.
- **Constraints get the droop for free.** Link rest lengths come from the particle positions.
  The skip links measure a drooped chord, so they hold the droop rather than straightening it;
  that's option B in `plan_sf_cloth_bending.md`. A bend-stiffness set, if present, rests at
  the drooped curvature, which is option C's drooped rest.
- **Nothing changes for unedited cloths.** If the armature matches the block, as it does after
  a plain import and export, nothing moves. A test covers that.

**Tests, written first:**

1. A vanilla cloth nif from `TT.SF_ASSETS` (the child ponytail), imported. Rotate one cloth
   bone's rest in Edit mode, export, and read the block back: that bone's reference pose has
   the new rotation, and the other bones are unchanged.
2. The same nif imported and exported with no edit: the cloth skeleton is unchanged, within
   float tolerance.

**Built 2026-11-11 (build 73), with two refinements found while testing:**

- **Only the bones the cloth drives are reposed.** Body bones such as `C_Hips` and `C_Head`
  keep the block's pose. The armature takes those from the reference skeleton, which needn't
  match what the cloth was authored against.
- **Bones are compared relative to their parent, not in model space.** The armature can sit
  a constant few millimetres from the cloth's skeleton, with the same rotations: 5 mm on the
  formal half dress, 1.3 mm on the child ponytail, and it varied with what earlier tests had
  loaded. That offset cancels between a bone and its parent; a bend doesn't. A bone is
  reposed when its parent-relative rotation changes by more than about 0.06° or its position
  by more than 5 mm.

Test: `TEST_SF_CLOTH_SKELETON_FROM_ARMATURE`. All 10 SF cloth tests pass, plus the pyn suite.

## Outcome (2026-11-11)

Drooping the cloth alone works. With the crowd skeletons restored to straight and both base
tails re-exported drooped (build 73), the tails look right in game. Drooping the skeleton as
well seemed to stack with the cloth's droop: the tail wrapped forward around the legs. So
the skeletons stay vanilla, and the droop lives in the tail nif.

## Re-posing the tail in Blender

The tail's Blender file needs the droop applied as the new rest pose, with everything
following:

- the tail bones;
- the render mesh;
- the sim mesh.

I'll write a script that copies the droop exactly from the skeleton Bad Dog posed. Each
joint's local rotation is saved in `C:\tmp\crowd_tail_pose\blender_tail_world.json`. [No need for this. I'll just re-pose skeleton and cloth in Blender.]

The script poses the tail bones, deforms the meshes with them, and applies the pose as the
new rest.

**One catch:** since the skin-loop fix, the sim particles are skinned only to `C_Tail_Root`,
so deforming the sim mesh by its skin weights wouldn't move it. The script instead moves each
particle with the tail bone it drives (the cloth's driven-bone mapping), or failing that, the
nearest tail bone. It leaves the skin weights as they are.

**Possible snag:** applying an armature deformation to a mesh with shape keys fails in Blender.
If the tail mesh has shape keys, the script has to carry them through. It will check first and
say so.

## Bad Dog's steps once it's built

1. Run the droop script in the tail's Blender file, male and female base tails.
2. Export each base tail.
3. Rebake the crowd tail variants with `sf_tintbake`.
4. In game, check:
   - a crowd fox whose tail doesn't simulate should hang;
   - one that does simulate should rest hanging and swing from there;
   - the player tail should do the same. It uses Extended Skeleton's straight bones, but the
     cloth should take over.

## Open questions

- **Base tails, or the variants?** The crowd variants are baked from the base tails, so the
  plan changes the base tails and rebakes. Is that right for both sexes?
- **The player's tail.** Should it droop too? If so, does Extended Skeleton's straight tail
  matter once the cloth holds the droop? That's the in-game check in step 4. If it does matter,
  the player race needs its own skeleton copy, the way the crowds have one.

[I don't know for sure. I'm happy with how the player tail hangs. Let's keep it simple - modify the base tail, bake crowd variants from there. If I don't like what I see for the player, we'll go back to the original scheme for player/FSFFoxRace tails only.]