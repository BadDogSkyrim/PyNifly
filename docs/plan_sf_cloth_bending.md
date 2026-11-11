# Starfield cloth: a tail that droops but has stiffness at each joint

**Goal (Bad Dog, 2026-10-23):** the tail is posed straight out, parallel to the ground. It should
droop under gravity, but resist bending at each joint, like a real tail. It should not hang like a
dishrag, float, or be held stiff in its posed shape.

**Where we are:** Felid's tail is a flat ladder: 24 particles, two rails, a rung at each of 12
steps. It has neighbour-to-neighbour links only, 1 solver iteration, and gravity −4.9. Lowering
gravity made it floaty. Adding 18 skip links (each particle to the one two along its rail) worked,
but made only a small difference.

## Why the skip links did so little

1. **They barely notice small bends.** A skip link spans two segments of length L. Bent by θ at
   the joint between them, its length is 2L·cos(θ/2). At 20° that's only 1.5% shorter than straight,
   at 10° 0.4%. The link only pushes back hard once the joint is well bent, so the tail droops almost
   freely at first. This is the main reason.
2. **One solver iteration.** Each step the solver makes one pass over 50 links that pull against
   each other, so no link gets fully satisfied. More iterations give every link more say.
3. **They pull towards straight.** Their rest length is the posed distance, so even when they do
   engage they pull towards the straight-out pose, which isn't the shape we want either.

## The options

| Option | What it does | Fits the goal? | Work |
| --- | --- | --- | --- |
| **A. More solver iterations** | `cloth_iterations` 1 → 4 or 8. Every link, skip links included, holds closer to its rest length. | Helps the skip links; still pulls towards straight. | None: it's a setting now. |
| **B. Pre-bent skip links** | Give each skip link the rest length of a joint already bent by an angle θ₀: 2L·cos(θ₀/2). The tail's natural shape becomes a droop of θ₀ per joint. Around a bent rest shape the link's length changes in proportion to the bend, so it resists from the start. | Close. A distance doesn't know which way it's bent, but gravity picks down. | Small: a rest angle on the links we add. |
| **C. Bend-stiffness constraints** | Vanilla's own joint spring (`hclBendStiffnessConstraintSetMx`, in 116 of 298 vanilla blobs). Each record spans two triangles that share an edge (4 particles), with a `bendStiffness` and a `restCurvature`, so it can rest bent. On a flat strip, bending across a rung *is* drooping. | Yes, this is the real tool: per-joint stiffness with a drooped rest shape. | Large. Felid's blob doesn't have the type, so its definition has to be copied in from a vanilla blob, plus a new constraint set (new items and new `PTCH` entries), the set added to the cloth's list, and its id added to the solver's run order. The weights and curvature also need working out from vanilla's data. |
| **D. Bone planes** | Keeps each particle on one side of a plane fixed to a bone (57 vanilla blobs). A plane tilted down by some angle caps the droop. | A stop, not a spring. Could go with B or C to stop it drooping too far. | Large, like C (new type). |
| **E. A different strip layout** | Make the strip upright, or a triangular tube, with diagonal links. Then drooping is bending *within* the strip's plane, and a braced strip resists that with plain links. | Yes, and strongly. | Largest: new particles, triangles and bone mapping. This is the tail generator. |
| **F. Lighter towards the tip** | Taper `cloth_mass` down the tail. Links then move the tip more and the root less. | Small effect at best. | None: per-particle mass is editable now. |
| ~~Local range~~ | Holds particles near their animated position. | No: it holds the tail in its straight posed shape. | — |

## Status (2026-10-23)

- **A tried:** better-behaved with the skip links (Bad Dog). The tail now runs 4 iterations.
- **C built** (uncommitted, build 53): `cloth_bend_stiffness` on the sim mesh. Set it above 0 and
  export adds a bend-stiffness set: a record at every edge two sim triangles share (20 on Felid's
  tail), resting in the rest shape, run after the standard links and before the stretch links.
  On a cloth that has a set, it reads back and changes in place.
  - The type definitions come from `pyn/sf_cloth_types.py`, the type section of the vanilla child
    ponytail with every object dropped. `scripts/make_sf_cloth_types.py` regenerates it.
  - The record formulas were fitted to vanilla's 3,256 records, and checked against the
    ponytail's. The weights and curvature match to 1e-7 on most records; a few vanilla records
    are a little off whatever the method.
  - Stiffness is one k for the whole set: `bendStiffness` = −k / Σ w²·invMass. Vanilla varies it
    record to record (painted per vertex).
  - Test files for Felid's tail, built on the current one: `C:\tmp\tail_bendstiff\k05` and `k09`.
- **Not yet:** a drooped rest shape (rest curvature from a bend angle instead of the straight
  pose); see the open questions.

## Recommendation

1. **Try A now.** Set `cloth_iterations` to 4 on the tail that has the skip links. It's free, and it
   tells us how much the solver was holding the skip links back.
2. **Then B,** if A is close but pulls too straight: a rest angle for the links we add, so they
   hold a droop instead of the straight pose. It's small, and stays within what the blob already
   has.
3. **C if B isn't enough.** It's what vanilla uses for exactly this. It's also our first new
   constraint type, and the type-copying it needs is the same machinery D and the tail generator
   will need.
4. **E belongs with the generator** (stage 3 in the cloth plan), once we know what stiffness feels
   right.

## Open questions

- B: one rest angle for every joint, or one that grows towards the tip (a curve)?
- C: how vanilla computes the four weights, `bendStiffness`'s sign and `restCurvature` from the rest
  shape. The ponytail's records have weights 0.5, 0.5, −0.5, −0.5, stiffness −0.4 and curvature ≈ 0
  (a flat rest).
