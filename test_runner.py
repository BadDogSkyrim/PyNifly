import os
from pathlib import Path
import sys
import importlib
import bpy

if 'PYNIFLY_DEV_ROOT' in os.environ:
    root_path = Path(os.environ['PYNIFLY_DEV_ROOT'])
    mod_path = root_path / 'PyNifly'
    tests_path = root_path / 'tests'

if str(mod_path) not in sys.path:
    sys.path.append(str(mod_path))

# if "PyNifly" in bpy.context.preferences.addons:
#     bpy.ops.preferences.addon_disable(module="PyNifly")
#     print(f"Disabled installed add-on: PyNifly")
# else:
#     print("Installed PyNifly add-on is not enabled.")

import PyNifly
PyNifly.unregister()
# importlib.reload(PyNifly)
# importlib.reload(PyNifly.nif)
# importlib.reload(PyNifly.nif.import_nif)
# importlib.reload(PyNifly.nif.export_nif)
# importlib.reload(PyNifly.tri)
# importlib.reload(PyNifly.tri.import_tri)
PyNifly.register()

import tests
importlib.reload(tests)
from tests.test_runner import doit

doit()
