""" Quick and Dirty Test Harness """

from blender_tests import *

print("""
=============================================================================
===                                                                       ===
===                               TESTING                                 ===
===                                                                       ===
=============================================================================
""")

# Tests of nifs with bones in a hierarchy
# target_tests = [
#     TEST_COLLISION_BOW_SCALE, TEST_BONE_HIERARCHY, TEST_COLLISION_BOW, 
#     TEST_COLLISION_BOW2, TEST_COLLISION_BOW3, TEST_COLLISION_BOW_CHANGE, 
#     TEST_ANIM_ANIMATRON, TEST_FACEGEN,]

# All tests with animations
# target_tests = [t for t in alltests if '_ANIM_' in t.__name__]

# All tests with collisions
# do_tests([t for t in alltests if 'COLL' in t.__name__])

do_tests(
    target_tests=[ TEST_SHADER_EYE ], run_all=False, stop_on_fail=True,
    # target_tests=[t for t in alltests if 'HKX' in t.__name__], run_all=False, stop_on_fail=True,
    # stop_on_fail=True
    )


