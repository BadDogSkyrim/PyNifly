"""
######################################## TESTS ########################################

Regression tests for animation readers (hkx/anim_fo4.py, hkx/anim_skyrim.py).

No Blender required. Run with:
  cd tests
  python -m tests.anim_tests

Or via the test runner pattern used by pynifly_tests.

######################################## TESTS ########################################
"""
import sys
import logging
from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
# Add io_scene_nifly/hkx to path so anim_fo4 can be imported directly
# (We can't import through hkx/__init__.py because it imports bpy.)
_test_dir = Path(__file__).resolve().parent
_project_root = _test_dir.parent
sys.path.insert(0, str(_project_root / "io_scene_nifly" / "hkx"))
sys.path.insert(0, str(_project_root / "io_scene_nifly"))
sys.path.insert(0, str(_test_dir))

import anim_fo4
import anim_skyrim
import test_tools as TT

log = logging.getLogger("pynifly")

# ── test data paths ─────────────────────────────────────────────────────────
_FO4_ANIM_DIR = _test_dir / "tests" / "FO4" / "Animations"
_SKYRIM_DIR = _test_dir / "tests" / "Skyrim"
_SKYRIMSE_DIR = _test_dir / "tests" / "SkyrimSE"
_OUT_DIR = _test_dir / "tests" / "Out"

_ROUNDTRIP_OUT = str(_OUT_DIR / "TEST_FO4_ANIM_ROUNDTRIP.hkx")
_ROUNDTRIP_DEATH_OUT = str(_OUT_DIR / "TEST_FO4_ANIM_ROUNDTRIP_DEATH.hkx")
_SKYRIM_ROUNDTRIP_OUT = str(_OUT_DIR / "TEST_SKYRIM_ANIM_ROUNDTRIP.hkx")
_SKYRIMSE_ROUNDTRIP_OUT = str(_OUT_DIR / "TEST_SKYRIMSE_ANIM_ROUNDTRIP.hkx")

executed_tests = {}


def execute_test(test_fn, stop_on_fail=True):
    name = test_fn.__name__
    try:
        test_fn()
        executed_tests[name] = "PASSED"
        print(f"  PASSED: {name}")
    except Exception as e:
        executed_tests[name] = "FAILED"
        print(f"  FAILED: {name}: {e}")
        if stop_on_fail:
            raise


# ═════════════════════════════════════════════════════════════════════════════
#  TESTS
# ═════════════════════════════════════════════════════════════════════════════

def TEST_READ_FO4_ANIM():
    """Read a FO4 run-forward-to-idle animation and verify header fields."""
    fp = str(_FO4_ANIM_DIR / "run_forward_to_idle.hkx")
    anim = anim_fo4.load_fo4_animation(fp)

    assert TT.is_eq(anim.num_tracks, 95, "Track count")
    assert TT.is_eq(anim.num_frames, 30, "Frame count")
    assert TT.is_eq(anim.num_blocks, 1, "Block count")
    assert TT.is_equiv(anim.duration, 0.9667, "Duration", e=0.001)
    assert TT.is_equiv(anim.frame_duration, 1.0/30.0, "Frame duration", e=0.001)
    assert TT.is_eq(anim.original_skeleton_name, "Root", "Skeleton name")
    assert TT.is_eq(len(anim.track_to_bone_indices), 95, "Binding index count")
    assert TT.is_eq(len(anim.tracks), 95, "Decompressed track count")


def TEST_FO4_ANIM_TRACKS():
    """Verify decompressed track data has the right shape and values."""
    fp = str(_FO4_ANIM_DIR / "run_forward_to_idle.hkx")
    anim = anim_fo4.load_fo4_animation(fp)

    # Every track should have exactly num_frames entries for each component
    for i, t in enumerate(anim.tracks):
        assert TT.is_eq(len(t.rotations), 30, f"Track {i} rotation frame count")
        assert TT.is_eq(len(t.translations), 30, f"Track {i} translation frame count")
        assert TT.is_eq(len(t.scales), 30, f"Track {i} scale frame count")

    # Track 0 (Root) should be identity throughout
    root = anim.tracks[0]
    assert TT.is_equiv(root.translations[0], [0, 0, 0], "Root translation", e=0.01)
    assert TT.is_equiv(root.rotations[0], [0, 0, 0, 1], "Root rotation", e=0.01)

    # Track 1 (COM) has significant translation — z changes from ~54 to ~56
    com = anim.tracks[1]
    assert TT.is_equiv(com.translations[0][2], 53.97, "COM z start", e=0.1)
    assert TT.is_equiv(com.translations[-1][2], 56.15, "COM z end", e=0.1)

    # Count tracks with actual rotation animation
    animated_rot = 0
    for t in anim.tracks:
        r0 = t.rotations[0]
        for r in t.rotations[1:]:
            dot = sum(r0[j] * r[j] for j in range(4))
            if abs(abs(dot) - 1.0) > 1e-5:
                animated_rot += 1
                break
    assert TT.is_eq(animated_rot, 61, "Animated rotation track count")

    # Count tracks with actual translation animation
    animated_trans = 0
    for t in anim.tracks:
        t0 = t.translations[0]
        for tr in t.translations[1:]:
            if any(abs(tr[j] - t0[j]) > 1e-5 for j in range(3)):
                animated_trans += 1
                break
    assert TT.is_eq(animated_trans, 5, "Animated translation track count")


def TEST_FO4_ANIM_ROUNDTRIP():
    """Write a loaded animation back to HKX, reload, and compare tracks."""
    fp = str(_FO4_ANIM_DIR / "Death1.hkx")
    orig = anim_fo4.load_fo4_animation(fp)

    # Write to tests/Out so result can be inspected
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = _ROUNDTRIP_DEATH_OUT
    anim_fo4.write_fo4_animation(tmp_path, orig)

    # Reload
    reloaded = anim_fo4.load_fo4_animation(tmp_path)

    # Compare header fields
    assert TT.is_eq(reloaded.num_tracks, orig.num_tracks, "Roundtrip track count")
    assert TT.is_eq(reloaded.num_frames, orig.num_frames, "Roundtrip frame count")
    assert TT.is_equiv(reloaded.duration, orig.duration, "Roundtrip duration", e=0.001)
    assert TT.is_eq(reloaded.original_skeleton_name, orig.original_skeleton_name,
                     "Roundtrip skeleton name")
    assert TT.is_eq(len(reloaded.track_to_bone_indices),
                     len(orig.track_to_bone_indices), "Roundtrip binding count")

    # Compare track data within tolerance (spline recompression is lossy)
    rot_tol = 0.05   # quaternion component tolerance
    pos_tol = 0.5    # translation tolerance
    scale_tol = 0.05

    max_rot_err = 0.0
    max_pos_err = 0.0
    for i in range(orig.num_tracks):
        ot = orig.tracks[i]
        rt = reloaded.tracks[i]
        assert TT.is_eq(len(rt.rotations), len(ot.rotations),
                         f"Track {i} rotation frame count")
        assert TT.is_eq(len(rt.translations), len(ot.translations),
                         f"Track {i} translation frame count")

        for f in range(len(ot.rotations)):
            # Quaternion comparison: handle sign flip (q == -q)
            oq = ot.rotations[f]
            rq = rt.rotations[f]
            dot = sum(oq[j] * rq[j] for j in range(4))
            if dot < 0:
                rq = [-x for x in rq]
            for j in range(4):
                err = abs(oq[j] - rq[j])
                if err > max_rot_err:
                    max_rot_err = err
                assert err < rot_tol, \
                    f"Track {i} frame {f} rot[{j}]: {oq[j]:.4f} vs {rq[j]:.4f} (err={err:.4f})"

        for f in range(len(ot.translations)):
            for j in range(3):
                err = abs(ot.translations[f][j] - rt.translations[f][j])
                if err > max_pos_err:
                    max_pos_err = err
                assert err < pos_tol, \
                    f"Track {i} frame {f} pos[{j}]: {ot.translations[f][j]:.4f} vs {rt.translations[f][j]:.4f} (err={err:.4f})"

        for f in range(len(ot.scales)):
            for j in range(3):
                err = abs(ot.scales[f][j] - rt.scales[f][j])
                assert err < scale_tol, \
                    f"Track {i} frame {f} scale[{j}]: err={err:.4f}"

    print(f"    Max rotation error: {max_rot_err:.6f}")
    print(f"    Max translation error: {max_pos_err:.6f}")


def TEST_FO4_ANIM_ROUNDTRIP_VARIETY():
    r"""Roundtrip 5 FO4 animations covering different characteristics.

    To verify in-game, copy each output over SneakIdle.hkx and sneak in FO4:
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_FO4_RT_Death1.hkx" "C:\steam\steamapps\common\Fallout 4\Data\Meshes\Actors\Character\Animations\MT\Neutral\SneakIdle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_FO4_RT_SneakIdle.hkx" "C:\steam\steamapps\common\Fallout 4\Data\Meshes\Actors\Character\Animations\MT\Neutral\SneakIdle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_FO4_RT_CoughingAfterCryo.hkx" "C:\steam\steamapps\common\Fallout 4\Data\Meshes\Actors\Character\Animations\MT\Neutral\SneakIdle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_FO4_RT_IdleSitChairLaserPistolCleaning.hkx" "C:\steam\steamapps\common\Fallout 4\Data\Meshes\Actors\Character\Animations\MT\Neutral\SneakIdle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_FO4_RT_PoseA_Talk_L5.hkx" "C:\steam\steamapps\common\Fallout 4\Data\Meshes\Actors\Character\Animations\MT\Neutral\SneakIdle.hkx" -Force
    """
    import struct as _s

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    test_files = [
        ("Death1.hkx",                          95,  81, 1),
        ("SneakIdle.hkx",                        95, 286, 2),
        ("CoughingAfterCryo.hkx",                94, 826, 4),
        ("IdleSitChairLaserPistolCleaning.hkx",  94, 501, 2),
        ("PoseA_Talk_L5.hkx",                    95, 207, 1),
    ]

    # Expected hk_2014 class hashes
    EXPECTED_HASHES = {
        'hkClassMember': 0xB0EFA719,
        'hkaAnimationContainer': 0x26859F4C,
        'hkMemoryResourceContainer': 0x1DE13A73,
        'hkaSplineCompressedAnimation': 0x8C3B5F7E,
        'hkaAnimationBinding': 0x0FAF9150,
    }

    rot_tol = 0.05
    pos_tol = 0.5

    for filename, exp_tracks, exp_frames, exp_blocks in test_files:
        in_path = str(_FO4_ANIM_DIR / filename)
        out_path = str(_OUT_DIR / f"TEST_FO4_RT_{filename}")

        orig = anim_fo4.load_fo4_animation(in_path)
        assert TT.is_eq(orig.num_tracks, exp_tracks, f"{filename} track count")
        assert TT.is_eq(orig.num_frames, exp_frames, f"{filename} frame count")

        anim_fo4.write_fo4_animation(out_path, orig)
        reloaded = anim_fo4.load_fo4_animation(out_path)

        # ── Data roundtrip checks ──
        assert TT.is_eq(reloaded.num_tracks, orig.num_tracks,
                         f"{filename} roundtrip track count")
        assert TT.is_eq(reloaded.num_frames, orig.num_frames,
                         f"{filename} roundtrip frame count")
        assert TT.is_equiv(reloaded.duration, orig.duration,
                            f"{filename} roundtrip duration", e=0.001)

        max_rot_err = 0.0
        for i in range(orig.num_tracks):
            for f in range(len(orig.tracks[i].rotations)):
                oq = orig.tracks[i].rotations[f]
                rq = reloaded.tracks[i].rotations[f]
                dot = sum(oq[j] * rq[j] for j in range(4))
                if dot < 0:
                    rq = [-x for x in rq]
                for j in range(4):
                    err = abs(oq[j] - rq[j])
                    if err > max_rot_err:
                        max_rot_err = err
                    assert err < rot_tol, \
                        f"{filename} track {i} frame {f} rot[{j}]: err={err:.4f}"

            for f in range(len(orig.tracks[i].translations)):
                for j in range(3):
                    err = abs(orig.tracks[i].translations[f][j] -
                              reloaded.tracks[i].translations[f][j])
                    assert err < pos_tol, \
                        f"{filename} track {i} frame {f} pos[{j}]: err={err:.4f}"

        # ── Binary format checks ──
        with open(out_path, 'rb') as fh:
            raw = fh.read()

        # File header
        assert raw[0:4] == b'\x57\xE0\xE0\x57', f"{filename} magic 1"
        assert raw[4:8] == b'\x10\xC0\xC0\x10', f"{filename} magic 2"
        assert _s.unpack_from('<i', raw, 0x0C)[0] == 11, f"{filename} file version"
        assert raw[0x10] == 8, f"{filename} ptr size"
        assert raw[0x28:0x36] == b'hk_2014.1.0-r1', f"{filename} version string"

        # Class hashes
        cn_abs = _s.unpack_from('<I', raw, 0x50 + 0x14)[0]
        cn_end = cn_abs + _s.unpack_from('<I', raw, 0x50 + 0x18)[0]
        classnames = {}
        pos = cn_abs
        while pos < cn_end:
            h, flags = _s.unpack_from('<IB', raw, pos)
            if h == 0xFFFFFFFF:
                break
            s = pos + 5
            e = raw.index(b'\x00', s)
            classnames[raw[s:e].decode('ascii')] = h
            pos = e + 1

        for cls, exp_hash in EXPECTED_HASHES.items():
            assert classnames.get(cls) == exp_hash, \
                f"{filename} {cls} hash {classnames.get(cls, 0):#010x} != {exp_hash:#010x}"

        # Global fixups (inter-object refs must be global)
        ds_abs = _s.unpack_from('<I', raw, 0x50 + 2*0x40 + 0x14)[0]
        gr = _s.unpack_from('<I', raw, 0x50 + 2*0x40 + 0x1C)[0]
        vr = _s.unpack_from('<I', raw, 0x50 + 2*0x40 + 0x20)[0]
        gc = 0
        pos = ds_abs + gr
        while pos + 12 <= ds_abs + vr:
            s, sec, d = _s.unpack_from('<III', raw, pos)
            if s == 0xFFFFFFFF:
                break
            gc += 1
            pos += 12
        assert TT.is_eq(gc, 6, f"{filename} global fixup count")

        # Quaternion encoding
        er = _s.unpack_from('<I', raw, 0x50 + 2*0x40 + 0x24)[0]
        sp_off = None
        pos = ds_abs + vr
        while pos + 12 <= ds_abs + er:
            o, sec, n = _s.unpack_from('<III', raw, pos)
            if o == 0xFFFFFFFF:
                break
            ss = cn_abs + n
            se = raw.index(b'\x00', ss)
            if raw[ss:se] == b'hkaSplineCompressedAnimation':
                sp_off = o
                break
            pos += 12

        # Animation type field at +0x10 (after 16-byte base class)
        assert _s.unpack_from('<I', raw, ds_abs + sp_off + 0x10)[0] == 3, \
            f"{filename} animation type must be 3 (SPLINE_COMPRESSED)"

        # Find data blob and check rot_quant
        lr = _s.unpack_from('<I', raw, 0x50 + 2*0x40 + 0x18)[0]
        pos = ds_abs + lr
        blob_off = None
        while pos + 8 <= ds_abs + gr:
            s, d = _s.unpack_from('<II', raw, pos)
            if s == 0xFFFFFFFF:
                break
            if s == sp_off + 0x98:
                blob_off = d
                break
            pos += 8
        assert blob_off is not None, f"{filename} data blob fixup"
        rq = (raw[ds_abs + blob_off] >> 2) & 0x0F
        assert TT.is_eq(rq, 1, f"{filename} rot_quant=1 (40-bit)")

        print(f"    {filename:45s} OK (rot_err={max_rot_err:.6f})")


def TEST_FO4_ANIM_QUATERNION_VALID():
    """All decompressed quaternions should be unit-length."""
    fp = str(_FO4_ANIM_DIR / "run_forward_to_idle.hkx")
    anim = anim_fo4.load_fo4_animation(fp)

    for i, t in enumerate(anim.tracks):
        for f, r in enumerate(t.rotations):
            length = sum(x**2 for x in r) ** 0.5
            assert TT.is_equiv(length, 1.0, f"Track {i} frame {f} quat length", e=0.01)


# ═════════════════════════════════════════════════════════════════════════════
#  SKYRIM TESTS
# ═════════════════════════════════════════════════════════════════════════════

def TEST_READ_SKYRIM_ANIM():
    """Read a Skyrim LE stagger animation and verify header fields."""
    fp = str(_SKYRIM_DIR / "1hm_staggerbacksmallest.hkx")
    assert anim_skyrim.is_skyrim_hkx(fp), "Should detect as Skyrim HKX"
    anim = anim_skyrim.load_skyrim_animation(fp)

    assert TT.is_eq(anim.num_tracks, 99, "Track count")
    assert TT.is_eq(anim.num_frames, 38, "Frame count")
    assert TT.is_eq(anim.num_blocks, 1, "Block count")
    assert TT.is_equiv(anim.duration, 1.2333, "Duration", e=0.001)
    assert TT.is_equiv(anim.frame_duration, 1.0/30.0, "Frame duration", e=0.001)
    assert TT.is_eq(len(anim.tracks), 99, "Decompressed track count")

    # Verify annotations were parsed
    assert TT.is_gt(len(anim.annotations), 0, "Has annotations")
    assert TT.is_eq(anim.annotations[0].text, "FootScuffRight", "First annotation text")


def TEST_SKYRIM_ANIM_TRACKS():
    """Verify decompressed Skyrim track data has correct shape."""
    fp = str(_SKYRIM_DIR / "1hm_staggerbacksmallest.hkx")
    anim = anim_skyrim.load_skyrim_animation(fp)

    for i, t in enumerate(anim.tracks):
        assert TT.is_eq(len(t.rotations), 38, f"Track {i} rotation frame count")
        assert TT.is_eq(len(t.translations), 38, f"Track {i} translation frame count")
        assert TT.is_eq(len(t.scales), 38, f"Track {i} scale frame count")

    # All decompressed quaternions should be unit-length
    for i, t in enumerate(anim.tracks):
        for f, r in enumerate(t.rotations):
            length = sum(x**2 for x in r) ** 0.5
            assert TT.is_equiv(length, 1.0, f"Track {i} frame {f} quat length", e=0.01)

    # Count animated tracks
    animated_rot = 0
    for t in anim.tracks:
        r0 = t.rotations[0]
        for r in t.rotations[1:]:
            dot = sum(r0[j] * r[j] for j in range(4))
            if abs(abs(dot) - 1.0) > 1e-5:
                animated_rot += 1
                break
    assert TT.is_eq(animated_rot, 61, "Animated rotation track count")


def TEST_SKYRIM_SKELETON():
    """Read the vanilla binary Skyrim skeleton (8-byte pointers) and verify bones."""
    fp = str(_SKYRIM_DIR / "skeleton.hkx")
    skel = anim_skyrim.load_skyrim_skeleton(fp)
    assert skel is not None, "Should parse binary skeleton"
    assert TT.is_eq(len(skel.bones), 99, "Bone count")
    assert TT.is_eq(skel.bones[0], "NPC Root [Root]", "Root bone name")
    assert TT.is_eq(skel.parents[0], -1, "Root parent is -1")
    assert TT.is_eq(skel.bones[4], "NPC COM [COM ]", "COM bone name")
    assert TT.is_eq(skel.parents[4], 0, "COM parent is root")
    assert TT.is_eq(len(skel.reference_pose), 99, "Reference pose count")
    root_pose = skel.reference_pose[0]
    assert TT.is_equiv(root_pose.rotation[3], 1.0, "Root rotation w ~1", e=0.01)


def TEST_SKYRIM_SKELETON_XML():
    """Read an XML-format Skyrim skeleton and verify bones match."""
    fp = str(_SKYRIM_DIR / "skeleton_xml.hkx")
    skel = anim_skyrim.load_skyrim_skeleton(fp)
    assert skel is not None, "Should parse XML skeleton"
    assert TT.is_eq(len(skel.bones), 99, "Bone count")
    assert TT.is_eq(skel.bones[0], "NPC Root [Root]", "Root bone name")
    assert TT.is_eq(skel.parents[4], 0, "COM parent is root")
    assert TT.is_eq(len(skel.reference_pose), 99, "Reference pose count")


def TEST_SKYRIM_TROLL_ANIM():
    """Read a troll (non-human) Skyrim animation."""
    fp = str(_SKYRIM_DIR / "troll_h2hattackleftd.hkx")
    anim = anim_skyrim.load_skyrim_animation(fp)

    assert TT.is_eq(anim.num_tracks, 54, "Troll track count")
    assert TT.is_eq(anim.num_frames, 57, "Troll frame count")
    assert TT.is_equiv(anim.duration, 1.8667, "Troll duration", e=0.001)
    assert TT.is_gt(len(anim.annotations), 0, "Troll has annotations")


def TEST_SKYRIM_ANIM_ROUNDTRIP():
    """Write a Skyrim animation to HKX, reload, and compare tracks."""
    fp = str(_SKYRIM_DIR / "1hm_staggerbacksmallest.hkx")
    orig = anim_skyrim.load_skyrim_animation(fp)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    anim_skyrim.write_skyrim_animation(_SKYRIM_ROUNDTRIP_OUT, orig)

    reloaded = anim_skyrim.load_skyrim_animation(_SKYRIM_ROUNDTRIP_OUT)

    assert TT.is_eq(reloaded.num_tracks, orig.num_tracks, "Roundtrip track count")
    assert TT.is_eq(reloaded.num_frames, orig.num_frames, "Roundtrip frame count")
    assert TT.is_equiv(reloaded.duration, orig.duration, "Roundtrip duration", e=0.001)

    rot_tol = 0.05
    pos_tol = 0.5
    max_rot_err = 0.0
    max_pos_err = 0.0
    for i in range(orig.num_tracks):
        ot = orig.tracks[i]
        rt = reloaded.tracks[i]
        assert TT.is_eq(len(rt.rotations), len(ot.rotations),
                         f"Track {i} rotation frame count")

        for f in range(len(ot.rotations)):
            oq = ot.rotations[f]
            rq = rt.rotations[f]
            dot = sum(oq[j] * rq[j] for j in range(4))
            if dot < 0:
                rq = [-x for x in rq]
            for j in range(4):
                err = abs(oq[j] - rq[j])
                if err > max_rot_err:
                    max_rot_err = err
                assert err < rot_tol, \
                    f"Track {i} frame {f} rot[{j}]: {oq[j]:.4f} vs {rq[j]:.4f} (err={err:.4f})"

        for f in range(len(ot.translations)):
            for j in range(3):
                err = abs(ot.translations[f][j] - rt.translations[f][j])
                if err > max_pos_err:
                    max_pos_err = err
                assert err < pos_tol, \
                    f"Track {i} frame {f} pos[{j}]: err={err:.4f}"

    print(f"    Max rotation error: {max_rot_err:.6f}")
    print(f"    Max translation error: {max_pos_err:.6f}")

    # Verify annotations survive roundtrip
    assert TT.is_eq(len(reloaded.annotations), len(orig.annotations),
                     "Roundtrip annotation count")
    for i, (oa, ra) in enumerate(zip(orig.annotations, reloaded.annotations)):
        assert TT.is_eq(ra.text, oa.text, f"Annotation {i} text")
        assert TT.is_equiv(ra.time, oa.time, f"Annotation {i} time", e=0.001)


def TEST_SKYRIM_HKX_DETECTION():
    """is_skyrim_hkx correctly distinguishes Skyrim from FO4 files."""
    skyrim_fp = str(_SKYRIM_DIR / "1hm_staggerbacksmallest.hkx")
    fo4_fp = str(_FO4_ANIM_DIR / "Death1.hkx")
    xml_fp = str(_SKYRIM_DIR / "skeleton.hkx")

    assert TT.is_eq(anim_skyrim.is_skyrim_hkx(skyrim_fp), True, "Skyrim anim detected")
    assert TT.is_eq(anim_skyrim.is_skyrim_hkx(fo4_fp), False, "FO4 anim not Skyrim")
    assert TT.is_eq(anim_skyrim.is_skyrim_hkx(xml_fp), True, "XML skeleton detected as Skyrim")
    assert TT.is_eq(anim_fo4.is_fo4_hkx(skyrim_fp), False, "Skyrim anim not FO4")
    assert TT.is_eq(anim_fo4.is_fo4_hkx(fo4_fp), True, "FO4 anim detected")


# ═════════════════════════════════════════════════════════════════════════════
#  SKYRIM SE TESTS (8-byte pointers)
# ═════════════════════════════════════════════════════════════════════════════

def TEST_READ_SKYRIMSE_ANIM():
    """Read a Skyrim SE stagger animation (8-byte ptrs) and verify header fields."""
    fp = str(_SKYRIMSE_DIR / "1hm_staggerbacksmallest.hkx")
    assert anim_skyrim.is_skyrim_hkx(fp), "Should detect as Skyrim HKX"
    anim = anim_skyrim.load_skyrim_animation(fp)

    assert TT.is_eq(anim.num_tracks, 99, "Track count")
    assert TT.is_eq(anim.num_frames, 38, "Frame count")
    assert TT.is_eq(anim.num_blocks, 1, "Block count")
    assert TT.is_equiv(anim.duration, 1.2333, "Duration", e=0.001)
    assert TT.is_equiv(anim.frame_duration, 1.0/30.0, "Frame duration", e=0.001)
    assert TT.is_eq(len(anim.tracks), 99, "Decompressed track count")

    assert TT.is_gt(len(anim.annotations), 0, "Has annotations")
    assert TT.is_eq(anim.annotations[0].text, "FootScuffRight", "First annotation text")


def TEST_SKYRIMSE_SKELETON():
    """Read the SE binary skeleton (8-byte pointers) and verify bones."""
    fp = str(_SKYRIMSE_DIR / "skeleton.hkx")
    skel = anim_skyrim.load_skyrim_skeleton(fp)
    assert skel is not None, "Should parse SE binary skeleton"
    assert TT.is_eq(len(skel.bones), 99, "Bone count")
    assert TT.is_eq(skel.bones[0], "NPC Root [Root]", "Root bone name")
    assert TT.is_eq(skel.parents[0], -1, "Root parent is -1")
    assert TT.is_eq(skel.bones[4], "NPC COM [COM ]", "COM bone name")
    assert TT.is_eq(len(skel.reference_pose), 99, "Reference pose count")


def TEST_SKYRIMSE_ANIM_TRACKS():
    """Verify SE decompressed tracks match LE (same animation, different encoding)."""
    le_fp = str(_SKYRIM_DIR / "1hm_staggerbacksmallest.hkx")
    se_fp = str(_SKYRIMSE_DIR / "1hm_staggerbacksmallest.hkx")
    le_anim = anim_skyrim.load_skyrim_animation(le_fp)
    se_anim = anim_skyrim.load_skyrim_animation(se_fp)

    assert TT.is_eq(se_anim.num_tracks, le_anim.num_tracks, "Track count matches LE")
    assert TT.is_eq(se_anim.num_frames, le_anim.num_frames, "Frame count matches LE")

    max_rot_err = 0.0
    max_pos_err = 0.0
    for i in range(le_anim.num_tracks):
        lt = le_anim.tracks[i]
        st = se_anim.tracks[i]
        for f in range(len(lt.rotations)):
            lq = lt.rotations[f]
            sq = st.rotations[f]
            dot = sum(lq[j] * sq[j] for j in range(4))
            if dot < 0:
                sq = [-x for x in sq]
            for j in range(4):
                err = abs(lq[j] - sq[j])
                if err > max_rot_err:
                    max_rot_err = err

        for f in range(len(lt.translations)):
            for j in range(3):
                err = abs(lt.translations[f][j] - st.translations[f][j])
                if err > max_pos_err:
                    max_pos_err = err

    print(f"    LE vs SE max rotation error: {max_rot_err:.6f}")
    print(f"    LE vs SE max translation error: {max_pos_err:.6f}")
    assert TT.is_lt(max_rot_err, 0.001, "LE vs SE rotation match")
    assert TT.is_lt(max_pos_err, 0.001, "LE vs SE translation match")


def TEST_SKYRIMSE_ANIM_ROUNDTRIP():
    """Write an SE animation to HKX, reload, and compare tracks."""
    fp = str(_SKYRIMSE_DIR / "1hm_staggerbacksmallest.hkx")
    orig = anim_skyrim.load_skyrim_animation(fp)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    anim_skyrim.write_skyrim_animation(_SKYRIMSE_ROUNDTRIP_OUT, orig, ptr_size=8)

    # Verify the output file has ptr_size=8
    import struct as _struct
    with open(_SKYRIMSE_ROUNDTRIP_OUT, 'rb') as f:
        hdr = f.read(0x14)
    assert TT.is_eq(hdr[0x10], 8, "Output file has ptr_size=8")

    reloaded = anim_skyrim.load_skyrim_animation(_SKYRIMSE_ROUNDTRIP_OUT)

    assert TT.is_eq(reloaded.num_tracks, orig.num_tracks, "Roundtrip track count")
    assert TT.is_eq(reloaded.num_frames, orig.num_frames, "Roundtrip frame count")
    assert TT.is_equiv(reloaded.duration, orig.duration, "Roundtrip duration", e=0.001)

    max_rot_err = 0.0
    max_pos_err = 0.0
    for i in range(orig.num_tracks):
        ot = orig.tracks[i]
        rt = reloaded.tracks[i]
        for f in range(len(ot.rotations)):
            oq = ot.rotations[f]
            rq = rt.rotations[f]
            dot = sum(oq[j] * rq[j] for j in range(4))
            if dot < 0:
                rq = [-x for x in rq]
            for j in range(4):
                err = abs(oq[j] - rq[j])
                if err > max_rot_err:
                    max_rot_err = err
                assert err < 0.05, \
                    f"Track {i} frame {f} rot[{j}]: err={err:.4f}"

        for f in range(len(ot.translations)):
            for j in range(3):
                err = abs(ot.translations[f][j] - rt.translations[f][j])
                if err > max_pos_err:
                    max_pos_err = err
                assert err < 0.5, \
                    f"Track {i} frame {f} pos[{j}]: err={err:.4f}"

    print(f"    Max rotation error: {max_rot_err:.6f}")
    print(f"    Max translation error: {max_pos_err:.6f}")

    # Verify annotations survive roundtrip
    assert TT.is_eq(len(reloaded.annotations), len(orig.annotations),
                     "SE roundtrip annotation count")
    for i, (oa, ra) in enumerate(zip(orig.annotations, reloaded.annotations)):
        assert TT.is_eq(ra.text, oa.text, f"SE annotation {i} text")
        assert TT.is_equiv(ra.time, oa.time, f"SE annotation {i} time", e=0.001)


def TEST_SKYRIMSE_HKX_BINARY_FORMAT():
    """Validate the binary structure of a written Skyrim SE HKX file.

    Catches format bugs that cause Skyrim CTD: wrong class hashes,
    incorrect struct sizes, missing fixups, wrong quantization.
    """
    import struct as _s

    # Write a roundtrip file
    fp = str(_SKYRIMSE_DIR / "1hm_staggerbacksmallest.hkx")
    orig = anim_skyrim.load_skyrim_animation(fp)
    out = str(_OUT_DIR / "TEST_SKYRIMSE_FORMAT_CHECK.hkx")
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    anim_skyrim.write_skyrim_animation(out, orig, ptr_size=8)

    with open(out, 'rb') as f:
        data = f.read()

    # ── File header ──
    assert data[0:4] == b'\x57\xE0\xE0\x57', "HKX magic"
    assert _s.unpack_from('<i', data, 0x0C)[0] == 8, "File version = 8 (hk_2010)"
    assert data[0x10] == 8, "Pointer size = 8 (SE)"
    version_str = data[0x28:0x38].split(b'\x00')[0]
    assert version_str == b'hk_2010.2.0-r1', f"Version string: {version_str}"

    # ── Class hashes (hk_2010, NOT hk_2014) ──
    # Parse classnames section
    cn_abs = _s.unpack_from('<I', data, 0x40 + 0x14)[0]
    cn_end_rel = _s.unpack_from('<I', data, 0x40 + 0x18)[0]
    cn_end = cn_abs + cn_end_rel
    classnames = {}
    pos = cn_abs
    while pos < cn_end:
        hash_val, flags = _s.unpack_from('<IB', data, pos)
        if hash_val == 0xFFFFFFFF:
            break
        str_start = pos + 5
        str_end = data.index(b'\x00', str_start)
        name = data[str_start:str_end].decode('ascii')
        classnames[name] = hash_val
        pos = str_end + 1

    # Verify hk_2010 hashes (these were wrong — had FO4 hk_2014 hashes)
    EXPECTED_HASHES = {
        'hkClass': 0x75585EF6,
        'hkClassMember': 0x5C7EA4C2,       # was 0x7EA4C2A4 (FO4)
        'hkaAnimationContainer': 0x8DC20333, # was 0x26859F4C (FO4)
        'hkMemoryResourceContainer': 0x4762F92A, # was 0x1DE13A73 (FO4)
        'hkaSplineCompressedAnimation': 0x792EE0BB,
        'hkaAnimationBinding': 0x66EAC971,
    }
    for name, expected_hash in EXPECTED_HASHES.items():
        assert name in classnames, f"Class {name} must be in classnames section"
        assert classnames[name] == expected_hash, \
            f"Class {name}: hash {classnames[name]:#010x} != expected {expected_hash:#010x}"

    # hkaDefaultAnimatedReferenceFrame must NOT be present (was erroneously included)
    assert 'hkaDefaultAnimatedReferenceFrame' not in classnames, \
        "hkaDefaultAnimatedReferenceFrame should not be in Skyrim animation files"

    # ── Section structure ──
    ds_abs = _s.unpack_from('<I', data, 0xA0 + 0x14)[0]
    local_rel = _s.unpack_from('<I', data, 0xA0 + 0x18)[0]
    global_rel = _s.unpack_from('<I', data, 0xA0 + 0x1C)[0]
    virt_rel = _s.unpack_from('<I', data, 0xA0 + 0x20)[0]
    exp_rel = _s.unpack_from('<I', data, 0xA0 + 0x24)[0]

    # ── Virtual fixups → find object offsets ──
    virt_entries = []
    pos = ds_abs + virt_rel
    while pos + 12 <= ds_abs + exp_rel:
        obj, sec, noff = _s.unpack_from('<III', data, pos)
        if obj == 0xFFFFFFFF:
            break
        # Resolve classname
        str_start = cn_abs + noff
        str_end = data.index(b'\x00', str_start)
        name = data[str_start:str_end].decode('ascii')
        virt_entries.append((obj, name))
        pos += 12

    assert TT.is_eq(len(virt_entries), 5, "Virtual fixup count (5 objects)")
    obj_names = [name for _, name in virt_entries]
    assert 'hkRootLevelContainer' in obj_names
    assert 'hkaAnimationContainer' in obj_names
    assert 'hkaSplineCompressedAnimation' in obj_names
    assert 'hkaAnimationBinding' in obj_names
    assert 'hkMemoryResourceContainer' in obj_names

    # ── Global fixups (inter-object references) ──
    global_count = 0
    pos = ds_abs + global_rel
    while pos + 12 <= ds_abs + virt_rel:
        src, sec, dst = _s.unpack_from('<III', data, pos)
        if src == 0xFFFFFFFF:
            break
        global_count += 1
        pos += 12
    assert TT.is_eq(global_count, 5,
                     "Global fixups (inter-object refs must be global, not local)")

    # ── hkRootLevelContainer layout ──
    # RLC has no serialized base class header — hkArray starts at offset 0
    rlc_off = [o for o, n in virt_entries if n == 'hkRootLevelContainer'][0]
    rlc_abs = ds_abs + rlc_off
    # The hkArray size field is at ptr_size (8) bytes into the array
    rlc_arr_size = _s.unpack_from('<I', data, rlc_abs + 8)[0]
    assert TT.is_eq(rlc_arr_size, 2, "RLC namedVariants count = 2")

    # ── hkMemoryResourceContainer size ──
    mrc_off = [o for o, n in virt_entries if n == 'hkMemoryResourceContainer'][0]
    mrc_abs = ds_abs + mrc_off
    mrc_end = ds_abs + local_rel  # last object before fixup tables
    mrc_size = mrc_end - mrc_abs
    assert mrc_size >= 80, \
        f"hkMemoryResourceContainer must be >= 80 bytes (was {mrc_size})"

    # ── Spline animation: quaternion encoding ──
    spline_off = [o for o, n in virt_entries if n == 'hkaSplineCompressedAnimation'][0]
    spline_abs = ds_abs + spline_off
    P = 8
    base_sz = 2 * P
    arr_sz = P + 8

    # Find the data blob via local fixup from spline+0x98 (data hkArray ptr)
    o_data_arr = spline_off + base_sz + 16 + P + arr_sz + 16 + 4 * arr_sz
    # Simpler: read directly from spline struct field offsets
    o_ann = base_sz + 16 + P       # annotationTracks hkArray offset
    o_post_ann = o_ann + arr_sz     # after annotationTracks
    o_block_offsets = ((o_post_ann + 28 + P - 1) & ~(P - 1))
    o_data = o_block_offsets + 4 * arr_sz  # skip 4 arrays

    # Find data blob by tracing the local fixup for the data hkArray ptr
    data_blob_off = None
    pos = ds_abs + local_rel
    while pos + 8 <= ds_abs + global_rel:
        src, dst = _s.unpack_from('<II', data, pos)
        if src == 0xFFFFFFFF:
            break
        if src == spline_off + o_data:
            data_blob_off = dst
            break
        pos += 8
    assert data_blob_off is not None, "Data blob fixup found"

    # Read first track mask byte — quantization must use rot_quant=1 (40-bit)
    blob_abs = ds_abs + data_blob_off
    mask_b0 = data[blob_abs]
    rot_quant = (mask_b0 >> 2) & 0x0F
    assert TT.is_eq(rot_quant, 1,
                     "Skyrim must use rot_quant=1 (40-bit), not 2 (48-bit FO4)")

    # ── Empty arrays must have DONT_DEALLOCATE flag ──
    o_float_block = o_block_offsets + arr_sz
    o_transform = o_float_block + arr_sz
    o_float = o_transform + arr_sz
    for name, arr_off in [('transformOffsets', o_transform),
                          ('floatOffsets', o_float)]:
        cap = _s.unpack_from('<I', data, spline_abs + arr_off + P + 4)[0]
        assert cap & 0x80000000, \
            f"{name} cap must have DONT_DEALLOCATE flag (got {cap:#010x})"

    print(f"    Binary format validation passed")


def TEST_SKYRIMSE_ANIM_ROUNDTRIP_VARIETY():
    r"""Roundtrip 5 Skyrim SE animations covering different characteristics.

    To verify in-game, copy each output over sneakmtidle.hkx and sneak in Skyrim SE:
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_SE_RT_sneakmtidle.hkx" "C:\steam\steamapps\common\Skyrim Special Edition\Data\Meshes\actors\character\animations\sneakmtidle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_SE_RT_sneak_1hmattackintro.hkx" "C:\steam\steamapps\common\Skyrim Special Edition\Data\Meshes\actors\character\animations\sneakmtidle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_SE_RT_chair_idlearmscrossedvar1.hkx" "C:\steam\steamapps\common\Skyrim Special Edition\Data\Meshes\actors\character\animations\sneakmtidle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_SE_RT_dialogueangrya.hkx" "C:\steam\steamapps\common\Skyrim Special Edition\Data\Meshes\actors\character\animations\sneakmtidle.hkx" -Force
        Copy-Item "C:\Modding\PyNifly\tests\tests\Out\TEST_SE_RT_bow_drawlight.hkx" "C:\steam\steamapps\common\Skyrim Special Edition\Data\Meshes\actors\character\animations\sneakmtidle.hkx" -Force
    """
    import struct as _s

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    test_files = [
        ("sneakmtidle.hkx",                99, 333, 2),
        ("sneak_1hmattackintro.hkx",        99,  10, 1),
        ("chair_idlearmscrossedvar1.hkx",   99, 275, 2),
        ("dialogueangrya.hkx",              99, 291, 2),
        ("bow_drawlight.hkx",               99,  51, 1),
    ]

    EXPECTED_HASHES = {
        'hkClass': 0x75585EF6,
        'hkClassMember': 0x5C7EA4C2,
        'hkaAnimationContainer': 0x8DC20333,
        'hkMemoryResourceContainer': 0x4762F92A,
        'hkaSplineCompressedAnimation': 0x792EE0BB,
        'hkaAnimationBinding': 0x66EAC971,
    }

    rot_tol = 0.05
    pos_tol = 0.5

    for filename, exp_tracks, exp_frames, exp_blocks in test_files:
        in_path = str(_SKYRIMSE_DIR / filename)
        out_path = str(_OUT_DIR / f"TEST_SE_RT_{filename}")

        orig = anim_skyrim.load_skyrim_animation(in_path)
        assert TT.is_eq(orig.num_tracks, exp_tracks, f"{filename} track count")
        assert TT.is_eq(orig.num_frames, exp_frames, f"{filename} frame count")

        anim_skyrim.write_skyrim_animation(out_path, orig, ptr_size=8)
        reloaded = anim_skyrim.load_skyrim_animation(out_path)

        # ── Data roundtrip checks ──
        assert TT.is_eq(reloaded.num_tracks, orig.num_tracks,
                         f"{filename} roundtrip track count")
        assert TT.is_eq(reloaded.num_frames, orig.num_frames,
                         f"{filename} roundtrip frame count")
        assert TT.is_equiv(reloaded.duration, orig.duration,
                            f"{filename} roundtrip duration", e=0.001)

        max_rot_err = 0.0
        for i in range(orig.num_tracks):
            for f in range(len(orig.tracks[i].rotations)):
                oq = orig.tracks[i].rotations[f]
                rq = reloaded.tracks[i].rotations[f]
                dot = sum(oq[j] * rq[j] for j in range(4))
                if dot < 0:
                    rq = [-x for x in rq]
                for j in range(4):
                    err = abs(oq[j] - rq[j])
                    if err > max_rot_err:
                        max_rot_err = err
                    assert err < rot_tol, \
                        f"{filename} track {i} frame {f} rot[{j}]: err={err:.4f}"

            for f in range(len(orig.tracks[i].translations)):
                for j in range(3):
                    err = abs(orig.tracks[i].translations[f][j] -
                              reloaded.tracks[i].translations[f][j])
                    assert err < pos_tol, \
                        f"{filename} track {i} frame {f} pos[{j}]: err={err:.4f}"

        # ── Annotation roundtrip ──
        assert TT.is_eq(len(reloaded.annotations), len(orig.annotations),
                         f"{filename} annotation count")
        for ai, (oa, ra) in enumerate(zip(orig.annotations, reloaded.annotations)):
            assert TT.is_eq(ra.text, oa.text, f"{filename} annotation {ai} text")
            assert TT.is_equiv(ra.time, oa.time, f"{filename} annotation {ai} time", e=0.001)

        # ── Binary format checks ──
        with open(out_path, 'rb') as fh:
            raw = fh.read()

        # File header (hk_2010, single magic, no padding block)
        assert raw[0:4] == b'\x57\xE0\xE0\x57', f"{filename} magic"
        assert _s.unpack_from('<i', raw, 0x0C)[0] == 8, f"{filename} file version"
        assert raw[0x10] == 8, f"{filename} ptr size"
        version_str = raw[0x28:0x38].split(b'\x00')[0]
        assert version_str == b'hk_2010.2.0-r1', f"{filename} version string"

        # Class hashes (hk_2010)
        cn_abs = _s.unpack_from('<I', raw, 0x40 + 0x14)[0]
        cn_end = cn_abs + _s.unpack_from('<I', raw, 0x40 + 0x18)[0]
        classnames = {}
        pos = cn_abs
        while pos < cn_end:
            h, flags = _s.unpack_from('<IB', raw, pos)
            if h == 0xFFFFFFFF:
                break
            s = pos + 5
            e = raw.index(b'\x00', s)
            classnames[raw[s:e].decode('ascii')] = h
            pos = e + 1

        for cls, exp_hash in EXPECTED_HASHES.items():
            assert classnames.get(cls) == exp_hash, \
                f"{filename} {cls} hash {classnames.get(cls, 0):#010x} != {exp_hash:#010x}"

        assert 'hkaDefaultAnimatedReferenceFrame' not in classnames, \
            f"{filename} must not contain hkaDefaultAnimatedReferenceFrame"

        # Global fixups (5 inter-object refs)
        ds_abs = _s.unpack_from('<I', raw, 0xA0 + 0x14)[0]
        gr = _s.unpack_from('<I', raw, 0xA0 + 0x1C)[0]
        vr = _s.unpack_from('<I', raw, 0xA0 + 0x20)[0]
        er = _s.unpack_from('<I', raw, 0xA0 + 0x24)[0]
        gc = 0
        pos = ds_abs + gr
        while pos + 12 <= ds_abs + vr:
            s, sec, d = _s.unpack_from('<III', raw, pos)
            if s == 0xFFFFFFFF:
                break
            gc += 1
            pos += 12
        assert TT.is_eq(gc, 5, f"{filename} global fixup count")

        # Virtual fixups — find spline object
        sp_off = None
        pos = ds_abs + vr
        while pos + 12 <= ds_abs + er:
            o, sec, n = _s.unpack_from('<III', raw, pos)
            if o == 0xFFFFFFFF:
                break
            ss = cn_abs + n
            se = raw.index(b'\x00', ss)
            if raw[ss:se] == b'hkaSplineCompressedAnimation':
                sp_off = o
                break
            pos += 12

        # Quaternion encoding — rot_quant=1 (40-bit)
        lr = _s.unpack_from('<I', raw, 0xA0 + 0x18)[0]
        pos = ds_abs + lr
        P = 8
        base_sz = 2 * P
        arr_sz = P + 8
        o_ann = base_sz + 16 + P
        o_post_ann = o_ann + arr_sz
        o_block_offsets = ((o_post_ann + 28 + P - 1) & ~(P - 1))
        o_data = o_block_offsets + 4 * arr_sz
        blob_off = None
        while pos + 8 <= ds_abs + gr:
            s, d = _s.unpack_from('<II', raw, pos)
            if s == 0xFFFFFFFF:
                break
            if s == sp_off + o_data:
                blob_off = d
                break
            pos += 8
        assert blob_off is not None, f"{filename} data blob fixup"
        rq = (raw[ds_abs + blob_off] >> 2) & 0x0F
        assert TT.is_eq(rq, 1, f"{filename} rot_quant=1 (40-bit)")

        print(f"    {filename:45s} OK (rot_err={max_rot_err:.6f})")


# ═════════════════════════════════════════════════════════════════════════════
#  Runner
# ═════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    TEST_READ_FO4_ANIM,
    TEST_FO4_ANIM_TRACKS,
    TEST_FO4_ANIM_ROUNDTRIP,
    TEST_FO4_ANIM_ROUNDTRIP_VARIETY,
    TEST_FO4_ANIM_QUATERNION_VALID,
    TEST_READ_SKYRIM_ANIM,
    TEST_SKYRIM_ANIM_TRACKS,
    TEST_SKYRIM_SKELETON,
    TEST_SKYRIM_SKELETON_XML,
    TEST_SKYRIM_TROLL_ANIM,
    TEST_SKYRIM_ANIM_ROUNDTRIP,
    TEST_SKYRIM_HKX_DETECTION,
    TEST_READ_SKYRIMSE_ANIM,
    TEST_SKYRIMSE_SKELETON,
    TEST_SKYRIMSE_ANIM_TRACKS,
    TEST_SKYRIMSE_ANIM_ROUNDTRIP,
    TEST_SKYRIMSE_HKX_BINARY_FORMAT,
    TEST_SKYRIMSE_ANIM_ROUNDTRIP_VARIETY,
]


def execute(testlist=None, stop_on_fail=True):
    tests = testlist or ALL_TESTS
    print(f"\n{'='*60}")
    print(f"  Running {len(tests)} animation test(s)")
    print(f"{'='*60}")
    for t in tests:
        execute_test(t, stop_on_fail=stop_on_fail)
    passed = sum(1 for v in executed_tests.values() if v == "PASSED")
    failed = sum(1 for v in executed_tests.values() if v == "FAILED")
    print(f"\n  Results: {passed} passed, {failed} failed\n")


if __name__ == "__main__":
    logging.basicConfig()
    log.setLevel(logging.DEBUG)
    execute(stop_on_fail=True)
