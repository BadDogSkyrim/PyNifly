""" Quick and Dirty Test Harness """

import importlib
import blender_tests as BT
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

BT.do_tests(
    target_tests=[ BT.TEST_HEADPART, ], # TEST_HEADPART, TEST_TRI2, TEST_SKEL_XML, TEST_SKEL_TAIL_HKX, TEST_AUXBONES_EXTRACT, TEST_DWEMER_CHEST, TEST_ALDUIN, TEST_KF, TEST_KF_RENAME, TEST_HKX, TEST_HKX_2
    # categories={'ANIMATION'},
    stop_on_fail=True
    )


