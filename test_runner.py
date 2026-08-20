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

# The tests live in tests/blender/*.py now. Reload those BEFORE the aggregator --
# reloading tests.blender_tests alone re-runs its star-imports against the modules
# already in sys.modules, so edits to a test file would be silently ignored.
# common first: everything else star-imports from it.
for _name in ['tests.blender.common'] + sorted(
        n for n in list(sys.modules)
        if n.startswith('tests.blender.') and n != 'tests.blender.common'):
    if _name in sys.modules:
        importlib.reload(sys.modules[_name])
if 'tests.blender_tests' in sys.modules:
    importlib.reload(sys.modules['tests.blender_tests'])
from tests.blender_tests import *

tests.blender_tests.do_tests(
    target_tests=[],
    test_all=True,
    stop_on_fail=False,
    )
