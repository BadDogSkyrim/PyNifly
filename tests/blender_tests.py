"""Automated tests for pyNifly export/import addon.

The tests themselves live in tests/blender/, split by domain; they are star-imported
here so `do_tests` sees them all in one namespace, exactly as when this was one file.

Convenient setup for running these tests here:
https://polynook.com/learn/set-up-blender-addon-development-environment-in-windows
"""

from .blender.common import *
from .blender.test_bodyparts import *
from .blender.test_geometry import *
from .blender.test_tri import *
from .blender.test_shaders import *
from .blender.test_collision import *
from .blender.test_fo4 import *
from .blender.test_skyrim import *
from .blender.test_starfield import *
from .blender.test_animation import *


# The canonical list lives in test_tools so the @TT.category decorator can validate
# against it. execute_test reads it here to find a test's minimum Blender version.
test_categories = TT.TEST_CATEGORIES



# --- Quick and Dirty Test Harness ---

def print_boxed(text, width=78):
    inner_width = width - 6
    top_bottom = "=" * width
    empty_line = "===" + " " * (inner_width) + "==="
    middle_line = f"==={text.center(inner_width)}==="

    print(top_bottom)
    print(empty_line)
    print(middle_line)
    print(empty_line)
    print(top_bottom)
    
    
def execute_test(t, executed_tests, stop_on_fail=True):
        # t = sys.modules[__name__].__dict__[t.__name__]
        if not t: return

        print (f"\n\n\n++++++++++++++++++++++++++++++ {t.__name__} ++++++++++++++++++++++++++++++")
        
        versions = [test_categories.get(c, (0,0)) for c in t.__dict__.get("category", set())]
        if bpy.app.version < max(versions) or (bpy.app.version < t.__dict__.get("min_blender_version", (0,0))):
            print (f"SKIPPING {t.__name__}: requires Blender version {max(versions)}, have {bpy.app.version}\n")
            executed_tests[t.__name__] = 'SKIP'
        elif t.__dict__.get("skip_test", None):
            print (f"SKIPPING {t.__name__}: marked to skip\n")
            executed_tests[t.__name__] = 'SKIP'
        else:
            if t.__doc__: print (f"{t.__doc__}")
            TTB.clear_all()

            if 'FO4' in t.__dict__.get("category", set()):
                bpy.context.preferences.filepaths.texture_directory = TTB.PYNIFLY_TEXTURES_FO4
            else:
                bpy.context.preferences.filepaths.texture_directory = TTB.PYNIFLY_TEXTURES_SKYRIM

            test_loghandler.start(t.__dict__.get("expected_errors", None))
            if stop_on_fail:
                try:
                    t()
                except (AssertionError, Exception):
                    breakpoint()
                    raise
                test_loghandler.finish()
                executed_tests[t.__name__] = 'PASS'
            else:
                try:
                    t()
                    test_loghandler.finish()
                    executed_tests[t.__name__] = 'PASS'
                except AssertionError:
                    executed_tests[t.__name__] = 'FAIL'
                except Exception as e:
                    log.exception(f"Test {t.__name__} failed with exception: {e}")
                    executed_tests[t.__name__] = 'FAIL'

        print (f"------------------------------ {t.__name__} ------------------------------\n")


def do_tests(
        target_tests=None,
        categories=None,
        stop_on_fail=False,
        startfrom=None,
        test_all=False,
        exclude=()):
    """Do tests in testlist. Can pass in a single test."""
    print_boxed("TESTING")

    active_tests = []
    if target_tests: 
        active_tests.extend(target_tests)
    if categories:
        for k, t in sys.modules[__name__].__dict__.items():
            if k.startswith('TEST_') and k not in exclude:
                if categories.intersection(t.__dict__.get("category", set())):
                    if t not in active_tests:
                        active_tests.append(t)
    if (not active_tests) or test_all: 
        all_tests = [t for k, t in sys.modules[__name__].__dict__.items() 
                        if k.startswith('TEST_') and k not in exclude]
        if active_tests:
            # Start with the requested tests then continue through the rest. This way when
            # working thorugh breaking tests, you don't start from the beginning every
            # time.
            i = all_tests.index(active_tests[0])
            for t in all_tests[i:] + all_tests[:i]:
                if t not in active_tests and t not in exclude:
                    active_tests.append(t)
        else:
            active_tests = all_tests
    
    executed_tests = {}

    startindex = 0
    if startfrom:
        try:
            startindex = active_tests.index(startfrom)
            active_tests = active_tests[startindex:]
        except:
            pass
    
    from time import perf_counter
    test_timings = []  # list of (name, seconds)

    for t in active_tests:
        if t not in executed_tests:
            _t0 = perf_counter()
            execute_test(t, executed_tests, stop_on_fail=stop_on_fail)
            test_timings.append((t.__name__, perf_counter() - _t0))

    print("\n\n===Slowest tests (top 30)===")
    for name, dt in sorted(test_timings, key=lambda x: -x[1])[:30]:
        print(f"  {dt:7.2f}s  {name}")
    _total = sum(dt for _, dt in test_timings)
    print(f"  -------\n  {_total:7.2f}s  TOTAL ({len(test_timings)} tests)")

    passed_tests = [t for t, v in executed_tests.items() if v == 'PASS']
    failed_tests = [t for t, v in executed_tests.items() if v == 'FAIL']
    skipped_tests = [t for t, v in executed_tests.items() if v == 'SKIP']

    print("\n\n===Succesful tests===")
    print(", ".join(passed_tests))
    print("\n\n===Failed tests===")
    print(", ".join(failed_tests))
    print("\n\n===Skipped tests===")
    print(", ".join(skipped_tests))
    if not failed_tests:
        msg = (f"""SUCCESS: {len(passed_tests):3d} test{"s" if len(passed_tests) != 1 else ""} """
            + f"""passed{"" if len(passed_tests) != 1 else " "}""")
        print_boxed(msg)
    else:
        print_boxed("TESTS FAILED")


def show_all_tests():
    for t in [t for k, t in sys.modules[__name__].__dict__.items() if k.startswith('TEST_')]:
        print(f"{t.__name__:25}{t.__doc__}")


if __name__ == "__main__":
    print_boxed("TESTING")

    if not bpy.data:
        # If running outside blender, just list tests.
        show_all_tests()
    else:
        # Tests of nifs with bones in a hierarchy
        # target_tests = [
        #     TEST_COLLISION_BOW_SCALE, TEST_BONE_HIERARCHY, TEST_COLLISION_BOW, 
        #     TEST_COLLISION_BOW2, TEST_COLLISION_BOW3, TEST_COLLISION_BOW_CHANGE, 
        #     TEST_ANIM_ANIMATRON, TEST_FACEGEN,]

        # All tests with animations
        # target_tests = [t for t in alltests if '_ANIM_' in t.__name__]

        # All tests with collisions
        # do_tests([t for t in alltests if 'COLL' in t.__name__])

        seen_categories = set()
        for t in [t for k, t in sys.modules[__name__].__dict__.items() if k.startswith('TEST_')]:
            seen_categories.update(t.__dict__.get("category", set()))
        print(f"Test categories: {sorted(seen_categories)}")

        do_tests(
            # target_tests=[ TEST_COLLISION_FO4_GEARDOOR, TEST_COLLISION_FO4_VAULT_SHELF, TEST_COLLISION_FO4_PHYSICS_SYSTEM ], stop_on_fail=True,
            # target_tests=[ TEST_PRETTY_BONE_POSITIONS ], run_all=False, stop_on_fail=True,
            # target_tests=[t for t in alltests if 'HKX' in t.__name__], run_all=False, stop_on_fail=True,
            )
