# Instructions for generating a crowd head

## Prerequisites

1. Regular race head with all performance and chargen morphs

## Creating the head

You will create one head for each phenotype.

1. Select eyes, arms, and head (consolidated or head, teeth, and tongue separately)
2. Dup and join. Name the new object for the phenotype, e.g. `crowdf_fox_md1`
3. Set the material to a crowd material
4. Move eye bones to center of eyes. Move BoneTranslations to match.
5. Rename the thin and overweight morphs `_thin` and `_overweight`. Add a morph named just `_` (same as base): it writes the plain, average nif. Any `_` key makes its own file, and with file keys only those files are written.
6. Average UV scale.
7. Hide left arm and eye. 
8. Pack UV islands.
9. Unhide left arm and eye. Superimpose left-side islands over right-side islands.
10. Select eyes, arms, head, and crowd head, crowd head active.
11. Run uv_transfer.py
12. Export the crowd head
13. Use the given uv_transfer command to create a batch file to generate all the texture layers (color, ao, normal, rough). Convert them to DDS with sf_texconv -- the material names the `.dds`, and a `.png` alone shows nothing in game.
14. Put the generated texture layers in the crowd head's shader
15. Export the crowd head again, all phenotypes (md2, md3...). Each `_` shape key writes its own nif and `.mesh`: `crowdf_fox_md1.nif` (from `_`), `crowdf_fox_md1_thin.nif`, `crowdf_fox_md1_overweight.nif`, each with a `_faceBones` companion -- vanilla's names. (Build 43 on; older exports used an `_average` key, which the bake still reads as the average.) Before exporting, check:
    - Starfield Geometry → weights per vertex is 0 (auto). At 1 the arms lose their biceps and elbow weights.
    - The crowd head has one material slot, its crowd material. With several, the active slot's material is the one written.
    - The `_faceBones` companion is a plain copy of the head, not a face rig. The game draws a crowd head from its companion, and the crowd skeleton has no face bones.
16. Paint is per UV layout, not per phenotype. Phenotypes that are reshapes of the same mesh share its UVs and its base textures; one that was joined separately needs its own map (step 11) and paint (step 13).

## Baking the variants

The head NIFs are only templates. NPCs wear baked variants: each a skin tone, dermaesthetic, complexion and eye colour composited into one colour texture, with its own `.mat`, written out as a nif per body type.

17. In the CK, give each phenotype a crowd-head addon in FSF.esm whose model for this sex is the head (any body type). Optional: without one, the builder uses `FSF_AA_CrowdHead_fox_md1_NOTPLAYABLE` as the template.
18. Deploy in Vortex, so the recipe's `heads` folder (under the game's Data) has the new head nifs.
19. Bake:
    ```
    python C:\Modding\PyNifly\scripts\sf_tintbake.py bake CrowdHead_fox_female.toml --dry-run --limit 3
    python C:\Modding\PyNifly\scripts\sf_tintbake.py bake CrowdHead_fox_female.toml --force
    ```
    The dry run lists each head with its body types and a few variant names. `--force` re-bakes textures that already exist -- needed after changing a head, its companion or its base textures. The bake writes the variants (colour textures, materials, nifs per body type, per-tone tails) into the recipe's `out` mod folder, and `CrowdHead_fox_female.variants.json` beside the recipe.
20. Deploy in Vortex again, once the bake has finished (it writes the DDS files last).
21. Build the plugin:
    ```
    python C:\Users\hughr\OneDrive\StarfieldDev\plugin_scripts\build_fsfnpc_fox.py
    ```
    It reads both sexes' manifests and writes `FSFNPC_Fox.esp`: a head list per sex and body type (`FSF_LL_Crowd_Heads_Fox[_Thin|_Overweight][_F]`), a test NPC and outfit for each, and a tail per skin tone. `--dry-run` reports without writing.
22. Check it:
    ```
    python C:\Modding\PyNifly\scripts\sf_racecheck.py --data "C:\Steam\steamapps\common\Starfield\Data" --plugin FSFNPC_Fox.esp --race FSFFoxCrowdRace
    ```
    It follows the NPCs' outfits to every head and tail and checks their nifs, meshes, materials, textures and companions.
23. In game: `bat fsfnpc_fox` places the test NPCs.