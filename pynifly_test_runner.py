import os
import sys
from pathlib import Path
import logging

# Load from install location
py_addon_path = Path(__file__).parent
if py_addon_path not in sys.path:
    sys.path.append(str(py_addon_path / "io_scene_nifly"))
dev_path = py_addon_path / "NiflyDLL" / "x64" / "debug" / "NiflyDLL.dll"

# Set working directory to tests folder
os.chdir(py_addon_path / "tests")

from tests.pynifly_tests import *
import tests.anim_tests as anim_tests

# Library is automatically loaded when pynifly is imported
# No need to call NifFile.Load() anymore

mylog = logging.getLogger("pynifly")
logging.basicConfig()
mylog.setLevel(logging.DEBUG)


# ############## TESTS TO RUN #############
# Test names on the command line run just those; otherwise everything. Exits 1 on failure.
_named = [globals()[n] for n in sys.argv[1:] if n.startswith('TEST_')]
if _named:
    failed = execute(testlist=_named, stop_on_fail=False)
else:
    failed = execute(stop_on_fail=False)
    failed += anim_tests.execute(stop_on_fail=False)
sys.exit(1 if failed else 0)
# execute(start=TEST_KF)
# execute(categories={"SHADER"})
#