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

import anim_fo4
import anim_skyrim
from . import test_tools as TT

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


# ═════════════════════════════════════════════════════════════════════════════
#  Runner
# ═════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    TEST_READ_FO4_ANIM,
    TEST_FO4_ANIM_TRACKS,
    TEST_FO4_ANIM_ROUNDTRIP,
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
