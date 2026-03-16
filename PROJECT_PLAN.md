# PyNifly Project Plan

Ideas, reminders, wish list, and open questions.

## Open Issues

## Wish List

### HKX annotation markers
- Import annotations as per-action pose markers instead of scene timeline markers, so each animation has its own set of annotations

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
- OSD import: need to resolve reference body from .osp project file so both outfit and body get sliders
- FO4 bhkRigidBody support: nifly library doesn't handle bhkRigidBodyCInfo2014 layout (fields after angularDamping are in different order than Skyrim's CInfo2010)
- FO4 collision COPY_TRANSFORMS constraint: currently zeroed for bhkNPCollisionObject because full influence moves parent nodes incorrectly in complex multi-body systems (gear door). Need a solution that works for simple single-body objects without breaking multi-body.

## Reminders

### FO4 skin bones
- Body NIFs have `_skin` bones parented to armature bones (e.g. `Pelvis_skin` -> `Pelvis`)
- Skin bone parenting information is not in the NIF node tree — use the bone dictionary
- Custom skeleton bones (e.g. Anus_01 from ZeX skeleton) won't be parented without a matching reference skeleton

### Elric (FO4 collision compiler)
- Elric converts legacy bhkCollisionObject/bhkRigidBody to FO4 native bhkNPCollisionObject/bhkPhysicsSystem
- **Block ordering matters** — Elric crashes if NIF blocks aren't in the right order. NifSkope may create them in wrong order.
- NifSkope's bhkRigidBody for FO4 uses `bhkRigidBodyCInfo2014` layout which differs from Skyrim's `CInfo2010` — our DLL (nifly) only reads the 2010 layout, so FO4 bhkRigidBody fields appear shifted/garbage
- Elric needs files under a `meshes/` folder to be happy

### FO4 Havok packfile physics — decoded fields (2026-03)
All offsets below are relative to the start of the body_props array data (PSD+0x10).

**Encoding note**: Several fields use "truncated float16" — the upper 16 bits of an IEEE 754 float32 stored as uint16. Decode: `value = struct.unpack('<f', struct.pack('<I', uint16_val << 16))[0]`. Encode: `uint16_val = struct.unpack('<I', struct.pack('<f', value))[0] >> 16`.

**Fields present in the packfile:**

| Offset | Encoding | Field |
|--------|----------|-------|
| +0x00 | truncated float16 (bytes 2-3) | friction |
| +0x04 | truncated float16 (bytes 6-7) | restitution |
| +0x08 | constant | unknown (always 0.0498) |
| +0x0c | constant | unknown (always 0xeeff7f7f) |
| +0x48 | float32 | gravityFactor |
| +0x50 | truncated float16 | maxLinearVelocity |
| +0x54 | truncated float16 | maxAngularVelocity |
| +0x58 | truncated float16 | linearDamping |
| +0x5c | truncated float16 | angularDamping |
| +0x60 | float32 | solver deactivation parameter (zeroed when solver=MAX) |
| +0x64 | float32 | solver deactivation parameter (zeroed when solver=MAX) |
| +0x84 | float32 | inverse mass (1/mass) |
| +0x88 | float32 | density (mass / collision_volume) |
| +0x10a | byte | collisionResponse (0=contact, 1=none) |

- **dyn_motion** (+0x20): CONSTANT engine defaults across all dynamic objects.
- **dyn_inertia** (+0x30): inertia diagonal at +0x20..+0x28 (3 floats), computed from shape + mass.
- **Static bodies**: No dyn_motion or dyn_inertia arrays.

**Fields NOT in the packfile** (engine-determined at runtime):
- penetrationDepth, motionSystem, deactivatorType, qualityType

**Vanilla defaults**: All vanilla objects use friction=0.5, restitution=0.4, linearDamping=0.1, angularDamping=0.05, gravityFactor=1.0, maxLinVel=104.4, maxAngVel=31.6. Verified across 10 objects (wood, ceramic, plastic, metal, rubber, stone) and confirmed with Elric-compiled output.

## Done

### Native HKX animation (2026-03)
- Import/export for Skyrim LE, SE, and FO4 — no hkxcmd dependency
- Fixed `game_rotations` global state bug (first-run animation scramble)
- Protected pre-existing armatures from NIF import bone modifications
- Skin bone parenting for FO4 HKX workflow
