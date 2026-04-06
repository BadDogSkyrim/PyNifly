import logging
import os
from importlib import reload
from . import test_tools
reload(test_tools)
try:
    from . import test_tools_bpy
    reload(test_tools_bpy)
except ImportError:
    pass
from . import test_nifchecker
reload(test_nifchecker)

# def running_in_blender():
#     try:
#         import bpy
#         return True
#     except ImportError:
#         return False

# log = logging.getLogger('pynifly')
# log.info(f"Running in blender: {running_in_blender()}")

# if running_in_blender():
#     from . import blender_tests
#     reload(blender_tests)
#     log.info("Reloaded blender_tests")