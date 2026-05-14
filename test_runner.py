import os
from pathlib import Path
import sys
import importlib


if 'PYNIFLY_DEV_ROOT' in os.environ:
    root_path = Path(os.environ['PYNIFLY_DEV_ROOT']) / 'PyNifly'
    mod_path = root_path / 'io_scene_nifly'
    tests_path = root_path / 'tests'

if str(mod_path) not in sys.path:
    sys.path.append(str(root_path))
#    sys.path.append(str(tests_path))

# if "PyNifly" in bpy.context.preferences.addons:
#     bpy.ops.preferences.addon_disable(module="PyNifly")
#     print(f"Disabled installed add-on: PyNifly")
# else:
#     print("Installed PyNifly add-on is not enabled.")


import tests
importlib.reload(tests)
if 'tests.blender_tests' in sys.modules:
    importlib.reload(sys.modules['tests.blender_tests'])
from tests.blender_tests import *

tests.blender_tests.do_tests(
    target_tests=[ TEST_COLLISION_MOPP_SEVMAGETOWER ],
    # categories={'FO4'},
    test_all=True,
    stop_on_fail=False,
    )
