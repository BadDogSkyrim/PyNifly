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

os.environ['PYNIFLY_DEV_ROOT'] = str(py_addon_path)

from tests.anim_tests import *

mylog = logging.getLogger("pynifly")
logging.basicConfig()
mylog.setLevel(logging.DEBUG)


# ############## TESTS TO RUN #############
execute(testlist=[TEST_FO4_ANIM_ROUNDTRIP ],
        stop_on_fail=True)
