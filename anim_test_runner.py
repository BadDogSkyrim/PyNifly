import os
import sys
from pathlib import Path
import logging

# Load from install location
py_addon_path = Path(__file__).parent
if str(py_addon_path / "io_scene_nifly") not in sys.path:
    sys.path.append(str(py_addon_path / "io_scene_nifly"))

# Set working directory to tests folder
os.chdir(py_addon_path / "tests")

# niflydll.py and test_runner.py both treat PYNIFLY_DEV_ROOT as the PARENT of the
# PyNifly checkout (they append 'PyNifly\...' to it). Setting it to the checkout
# itself yields ...\PyNifly\PyNifly\... and the DLL never loads.
os.environ['PYNIFLY_DEV_ROOT'] = str(py_addon_path.parent)

from tests.anim_tests import *

mylog = logging.getLogger("pynifly")
logging.basicConfig()
mylog.setLevel(logging.DEBUG)


# ############## TESTS TO RUN #############
# Runs everything in anim_tests.ALL_TESTS. To work on a single test, pass it:
#   execute(testlist=[TEST_FO4_ANIM_ROUNDTRIP], stop_on_fail=True)
execute(stop_on_fail=False)
