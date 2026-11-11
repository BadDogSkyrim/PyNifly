# Instructions for generating a crowd head

## Prerequisites

1. Regular race head with all performance and chargen morphs

## Create the head/arms mesh

A crowd race puts head and arms in one ARMA mesh with its own UV and texture set.

1. Select eyes, arms, and head (consolidated or head, teeth, and tongue separately)
2. Dup and join, with the **head active**. The join keeps the active object's settings, and an imported eye's Weights per vertex is 1: a head joined into an eye exports every vertex on one bone and warps in game (export warns). Name the new object for the phenotype, e.g. `crowdf_fox_md1`
3. Set the "crowd" flag in the Starfield properties panel.
4. Set the material to a crowd material
5. Move eye bones to center of eyes. Move BoneTranslations to match.
6. Rename the thin and overweight morphs `_thin` and `_overweight`. Add a morph named just `_` (same as base): it writes the plain, average nif. Any `_` key makes its own file, and with file keys only those files are written.
7. Average UV scale.
8. Hide left arm and eye. (They use the same texture areas as the right side.)
9. Pack UV islands.
10. Unhide left arm and eye. Superimpose left-side islands over right-side islands.
11. Select eyes, arms, head, and crowd head, crowd head active.
12. Run `uv_transfer.py`. Note its last message in the console log is a command for building the associated texture files.
13. Export the crowd head

## Generate template textures

The crowd heads need textures assembled from the original head part textures.

13. Use the given uv_transfer command to create a batch file to generate all the texture layers (color, ao, normal, rough). Run the batch file.
14. Convert new texture files to DDS with `sf_textconv.py`.
16. Back in blender, put the generated texture layers in the crowd head's shader (this may not be necessary, but make things look better).

## Generate crowd heads for all phenotypes

Now that we have the base textures, we can export all the phenotypes (head shapes) we've designed.

Paint is per UV layout, not per phenotype. Phenotypes that are reshapes of the same mesh share its UVs and its base textures.

16. Export the crowd head again, all phenotypes (md2, md3...). Each `_` shape key writes its own nif and `.mesh`: `crowdf_fox_md1.nif` (from `_`), `crowdf_fox_md1_thin.nif`, `crowdf_fox_md1_overweight.nif`, each with a `_faceBones` companion -- vanilla's names. (Build 43 on; older exports used an `_average` key, which the bake still reads as the average.) Before exporting, check:
    - Starfield Geometry → weights per vertex is 0 (auto). At 1 the arms lose their biceps and elbow weights.
    - The crowd head has one material slot, its crowd material. With several, the active slot's material is the one written.
    - The `_faceBones` companion is a plain copy of the head, not a face rig. The game draws a crowd head from its companion, and the crowd skeleton has no face bones.
    - Starfield Morphs → `crowd` is on, and `performance_path` is where the crowd morph goes (one shared by all phenotypes, or one each with `{shape}`). With `crowd` on, export writes only the performance `morph.dat`, holding vanilla's 11 crowd keys with each R key merged into its L, averaged where both move a vertex (crowd faces animate both sides from the L keys), and no chargen file. Build 47 on.
17. In xEdit, create crowd head records for each phenotype you generated.
    - "Hide Head" first person flag
    - Assigned to the crowd race (the plugin build copies these and puts them on `HumanCrowdRace`)
    - Model references the phenotype nif
    - Needs a MRPH record. All the phenotypes can use the same `morph.dat`.

## Beards (optional)

A crowd head's jaw and chin are in its mesh, and nothing morphs a beard to fit it (crowd actors have no chargen morph values), so each beard is fitted to its head and exported with it.

- Keep the beard in the head's .blend with the same `_`, `_thin`, `_overweight` shape keys, so one export writes all body types.
- Export it into a `Beards` folder under the heads folder, named `<head>_<beard>.nif`, e.g. `Beards\Crowd_Head_Fox_md1_Ruff01.nif` (plus `_thin`, `_overweight`). Every body type the head has needs its beard; the bake refuses a gap.
- Give it its performance morph so it follows the face: Starfield Morphs → `crowd` on, `performance_path` one folder per head's beard, e.g. `Meshes\Morphs\FSFFox\Male\Performance\Crowd_Fox_md1_Ruff04`. In the recipe's `[beards]`, `morphs = "Meshes/Morphs/FSFFox/Male/Performance/{beard}"` (`{beard}` is `<head>_<beard>`); the bake checks each `morph.dat` is there, and the builder links it to the beard addon.
- In the recipe, a `[beards]` table: `percent` (about how many variants get a beard: 100 all, 0 none; default 50; at 100 a head with no beard is left out, with a warning) and `colors`, the Simple AVM group the beard addon names for its colour (`FSFFox_Crowd_Beard_Colors`).
- Variant names end `b<beard>` or `b0` (e.g. `…_sk2_d1c3e5bRuff01`). Each gets one of its head's beards, or none, picked the same way every bake. The beard doesn't change the texture, so the texture, material and nif are named without it.

## Bake crowd head variants

The template textures are just the base level, not including the postblenddetails layers. This step creates unique crowd heads, textures, and materials for every phenotype, body weight, skin tone, eye color, and combination of postblenddetail layers. 

18.  Deploy in Vortex, so the recipe's `heads` folder (under the game's Data) has the new head nifs.
19.  If necessary, create the recipe `.TOML` file. (Only has to be done once.) A recipe paints one UV layout and starts the faces from one phenotype's tone list. Heads that share a layout share a recipe, even when they are different meshes (other phenotypes, or decimated): the bake paints in UV space and never looks at the head's vertices. Heads with a different layout, or that need a different phenotype's tone list, need a recipe of their own. When they share a folder, `heads` can be a pattern on the nif names, e.g. `.../Mesh/Female/crowdf_fennec_*.nif`. Give each recipe `race_config`, the furrifier's race file (`C:/Modding/Starfield/sf_furrify/races/FSFFoxRace.toml`): each head is then baked only in the tones of the breed whose `crowd_heads` match it, the same tones the plugin build will keep, and a head no breed takes is an error. The dry run shows each head's breed and tones.
20.  Bake:
    ```
    python C:\Modding\PyNifly\scripts\sf_tintbake.py bake CrowdHead_fox_female.toml --dry-run --limit 3
    python C:\Modding\PyNifly\scripts\sf_tintbake.py bake CrowdHead_fox_female.toml --force
    ```
    The dry run lists each head with its body types and a few variant names. `--force` re-bakes textures that already exist -- needed after changing a head, its companion or its base textures. The bake writes the variants (colour textures, materials, nifs per body type, per-tone tails) into the game's Data folder, or the folder you name with `--out`, and `CrowdHead_fox_female.variants.json` beside the recipe.
21.  If you used `--out` with a mod folder, deploy in Vortex again.

## Build the plugin

The furrifier builds crowds along with everything else, into one plugin. Crowd actors, their race and the crowd regions aren't touched: the crowd outfits change, so each spawn picks a race at the scheme's proportions. A head addon names a male and a female model, paired within a breed whatever their tones, since an actor only shows its own sex's head. Its tail addon likewise has each sex's tail in that sex's tone.

22. Say which heads belong to what, once:
    - In the race's TOML, `crowd_manifests` under `[race]` lists every recipe's manifest from the bake (one per recipe, so one per UV layout per sex).
    - Each breed with a weight has `crowd_heads`, globs on variant names, e.g. `["Crowd_Fen_*", "crowdf_fennec_*"]`. Its tones narrow them, per sex: `skin_tone_override` (and `skin_tone_override_female`), else the race's `skin_tones` (and `skin_tones_female`).
    - In `scheme.toml`, `[proportions]` gives each race, and `_HUMAN` if you want humans, a relative weight. A race alone means all of them.
23. Build, from `C:\Modding\Starfield\sf_furrify`:
    ```
    python sf_furrify.py --crowd-test --crowd-skeleton C:\Modding\Starfield\Mods\FSF_test
    ```
    It writes `FSFNPC.esm` to Data (master + light), holding the outfit overrides, mix lists, head lists and armors, tails and beard addons. `--crowd-skeleton` copies the crowd skeleton, which has the tail bones, over vanilla's `Actors\human_crowd\CharacterAssets` under that folder. `--crowd-test` adds six test NPCs and a batch file. To test crowds alone, add `--only NoSuchNPC`: `--only` leaves out the named NPCs it doesn't match. Add `FSFNPC.esm` to the load order and disable `FSFNPC_Fox.esm` if it's still there, then deploy in Vortex.
24. Check it:
    ```
    python C:\Modding\PyNifly\scripts\sf_racecheck.py --data "C:\Steam\steamapps\common\Starfield\Data,C:\Modding\Starfield\00StarfieldAssets" --plugin FSFNPC.esm --race HumanCrowdRace
    ```
    It follows the crowd NPCs' outfits to every head and tail and checks their nifs, meshes, materials, textures and companions.
25. In game: `bat fsfnpc_crowd` places the test NPCs, foxes whatever the proportions.
