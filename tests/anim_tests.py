"""
######################################## TESTS ########################################

Regression tests for the FO4 animation reader (hkx/anim_fo4.py).

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
from . import test_tools as TT

log = logging.getLogger("pynifly")

# ── test data paths ─────────────────────────────────────────────────────────
_FO4_ANIM_DIR = _test_dir / "tests" / "FO4" / "Animations"
_OUT_DIR = _test_dir / "tests" / "Out"

_ROUNDTRIP_OUT = str(_OUT_DIR / "TEST_FO4_ANIM_ROUNDTRIP.hkx")
_ROUNDTRIP_DEATH_OUT = str(_OUT_DIR / "TEST_FO4_ANIM_ROUNDTRIP_DEATH.hkx")

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
#  Runner
# ═════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    TEST_READ_FO4_ANIM,
    TEST_FO4_ANIM_TRACKS,
    TEST_FO4_ANIM_ROUNDTRIP,
    TEST_FO4_ANIM_QUATERNION_VALID,
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
