# PyNifly Project Plan

Ideas, reminders, wish list, and open questions.

## Open Issues

### Armature compatibility check (`find_compatible_arma`)
- Currently skips compatibility check entirely for pre-existing (user-selected) armatures
- Original purpose: reject incompatible armatures when a NIF combines parts from different skeletons (e.g. human hood + draugr helmet with different bind positions)
- Problem: HKX skeleton and NIF body describe the same skeleton but have tiny floating point differences (~0.02) from different transform computation paths, causing false rejection
- Need a better solution — maybe larger epsilon, or only reject on large mismatches, or let the user override

## Wish List

### Rig support
- Should be possible to attach a control rig (e.g. Rigify) to an imported HKX skeleton
- Control rig drives armature bones via constraints, bake down for export
- Need community input on existing Bethesda skeleton Rigify presets

## TODO

- Check import of loadscreen NIFs with poses
- Import the full ZeX skeleton into our bone lists

## Reminders

### FO4 skin bones
- Body NIFs have `_skin` bones parented to armature bones (e.g. `Pelvis_skin` -> `Pelvis`)
- Skin bones aren't in the NIF node tree or reference skeleton — parenting is by naming convention
- Custom skeleton bones (e.g. Anus_01 from ZeX skeleton) won't be parented without a matching reference skeleton

## Done

### Native HKX animation (2026-03)
- Import/export for Skyrim LE, SE, and FO4 — no hkxcmd dependency
- Fixed `game_rotations` global state bug (first-run animation scramble)
- Protected pre-existing armatures from NIF import bone modifications
- Skin bone parenting for FO4 HKX workflow
