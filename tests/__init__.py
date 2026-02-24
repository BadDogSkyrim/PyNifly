import logging 
import os
from importlib import reload
from . import test_tools
reload(test_tools)

def running_in_blender():
    return "BLENDER_SYSTEM_SCRIPTS" in os.environ

if running_in_blender():
    from . import blender_tests
    reload(blender_tests)
    log = logging.getLogger('pynifly')
    log.info("Reloaded blender_tests")