# Plan: export format follows the game folder

**Status 2026-11-03:** built as answered (warn only), build 69, uncommitted. As built:
- `gamefinder.game_of_path()` and `wrong_game_folder_warning()`. Nif export, HKX animation
  export and HKX skeleton export warn, in the console and the status bar.
- No new installed-game finders. Steam always installs under the game's own folder name, so
  the name match catches every Steam install. The three existing finders (FO4, Skyrim LE/SE)
  still catch Bethesda-launcher and moved installs.
- No live switching in the dialog (your answer to Q1).
- Tests: TEST_GAME_OF_PATH, TEST_EXPORT_NIF_WRONG_GAME_FOLDER, TEST_EXPORT_NIF_RIGHT_GAME_FOLDER,
  TEST_HKX_EXPORT_WRONG_GAME_FOLDER.

For review before building. Prompted by the dog-tail check: three Skyrim LE tail HKX files exported
into `Skyrim Special Edition\Data`, where SE can't read them, so nothing changed in game and
nothing said why.

**Rule:** when you export a nif or HKX file into a game's own folder, the format matches that game.

## Which folder is which game

An export path is "in a game folder" when it's under that game's `Data` directory. Two ways to
find those directories, both checked:

1. **Installed games.** `gamefinder.py` already finds FO4, Skyrim LE and Skyrim SE from Steam's
   library list and the registry; texture lookup uses it. Add: Starfield, Fallout 3, New Vegas,
   Fallout 76, Skyrim VR and Fallout 4 VR. Cached once per session, as now.
2. **By name.** A path containing `\<install folder>\Data\`, using each game's standard install
   folder name (`Skyrim Special Edition`, `Skyrim`, `Fallout 4`, `Starfield`, `Fallout New Vegas`,
   `Fallout 3 goty`, ...). That catches a copied install, a second drive, or a game Steam
   doesn't list.

Not detected: mod manager staging folders (MO2 `mods\`, Vortex staging). Nothing in those paths
says which game they're for. Exporting there works as it does today.

VR versions use their flat game's formats: Skyrim VR counts as Skyrim SE, FO4 VR as FO4.

## What "format" means

| File | Setting | Game folder decides |
| --- | --- | --- |
| nif | Target Game | the game (Skyrim LE vs SE vs FO4 ... all differ) |
| HKX animation, skeleton | Game | FO4 vs Skyrim LE vs Skyrim SE |

## What export does

1. **The dialog follows the folder.** As you browse, when the chosen path enters a game folder,
   the Target Game / Game setting switches to that game. (Blender calls the dialog's `check()` on
   each path change, so this is live: you see it change before you click Export.) It switches
   only when the *detected* game changes, so once you're in a folder you can still set it to
   something else by hand.
2. **A mismatch at export warns.** If the setting still doesn't match the folder when you click
   Export (you changed it, or a script ran the export), the file is written as asked and export
   reports a warning naming both: "Exported as Skyrim LE into a Skyrim SE folder; the game can't
   load it." Not an error, because a deliberate mismatch can be legitimate (writing LE into an
   SE folder to convert it with another tool).
3. **Scripts.** `bpy.ops.export_scene.pynifly(...)` and the HKX operators get the same warning;
   nothing switches silently under a script.

## Tests (test-first)

- Path matching, no Blender: a path under each game's install name maps to that game; a
  path outside any game folder maps to none; case and slashes don't matter.
- HKX: export an LE armature to a path under a fake `...\Skyrim Special Edition\Data\` folder
  with Game left as LE. The warning is reported and the file is LE.
- HKX: the dialog's `check()` with that path sets Game to Skyrim SE.
- Nif: the same two for Target Game, with a FO4 nif into a Skyrim SE folder.
- Real install detection isn't unit-tested (it depends on the machine). One smoke test logs
  what was found.

## Questions for you

1. Live switching in the dialog plus a warning at export: OK? Or would you rather it only warned? -Warn only
2. Warning, not error, for a mismatch at export: OK? - yes
