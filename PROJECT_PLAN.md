# PyNifly Project Plan

Ideas, reminders, wish list, and open questions.

## Open Issues

## Wish List

### Rig support
- Should be possible to attach a control rig (e.g. Rigify) to an imported HKX skeleton
- Control rig drives armature bones via constraints, bake down for export
- Need community input on existing Bethesda skeleton Rigify presets

## TODO

- Check import of loadscreen NIFs with poses
- Import the full ZeX skeleton into our bone lists
- Import of full FO4 animatron with animations
- Correct handling of Dwemer chest
- Creating an auxbones skeleton from scratch (workflow TBD)

## Reminders

### FO4 skin bones
- Body NIFs have `_skin` bones parented to armature bones (e.g. `Pelvis_skin` -> `Pelvis`)
- Skin bone parenting information is not 
- Custom skeleton bones (e.g. Anus_01 from ZeX skeleton) won't be parented without a matching reference skeleton

## Done

### Native HKX animation (2026-03)
- Import/export for Skyrim LE, SE, and FO4 — no hkxcmd dependency
- Fixed `game_rotations` global state bug (first-run animation scramble)
- Protected pre-existing armatures from NIF import bone modifications
- Skin bone parenting for FO4 HKX workflow
