import os
import sys
from pathlib import Path
import logging

# Load from install location
py_addon_path = Path(__file__).parent
if py_addon_path not in sys.path:
    sys.path.append(str(py_addon_path))
dev_path = py_addon_path / "NiflyDLL" / "x64" / "debug" / "NiflyDLL.dll"
hkxcmd_path = py_addon_path / "hkxcmd.exe"

# Set working directory to tests folder
os.chdir(py_addon_path / "tests")

from io_scene_nifly.pyn import xmltools
xmltools.XMLFile.SetPath(hkxcmd_path)
from io_scene_nifly.pyn.pynifly import NifFile
from tests.pynifly_tests import *

dev_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], dev_path))

mylog = logging.getLogger("pynifly")
logging.basicConfig()
mylog.setLevel(logging.DEBUG)



# ############## TESTS TO RUN #############
execute(
    # testlist=[TEST_RENAME_NODES],
    stop_on_fail=True,
    )
# execute()
# execute(start=TEST_KF)
# execute(categories={"SHADER"})
#