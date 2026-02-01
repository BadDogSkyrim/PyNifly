""" Quick and Dirty Test Harness """

from pathlib import Path

import importlib
from . import blender_tests as BT
importlib.reload(BT)

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

def doit():
    BT.do_tests(
        target_tests=[ BT.TEST_HEADPART, ], 
        # categories={'HKX'},
        test_all=True,
        stop_on_fail=True,
        )


