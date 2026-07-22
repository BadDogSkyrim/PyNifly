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

import tests
importlib.reload(tests)
if 'tests.blender_tests' in sys.modules:
    importlib.reload(sys.modules['tests.blender_tests'])
from tests.blender_tests import *

tests.blender_tests.do_tests(
    test_all=True,
    stop_on_fail=False,
    )
