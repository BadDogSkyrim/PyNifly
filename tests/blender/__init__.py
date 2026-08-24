"""Blender-side test suite, split by domain.

Every module here does `from .common import *` for the shared imports, the log
handler and the shared helpers, then defines its TEST_* functions. `..blender_tests`
star-imports all of them into one namespace, which is what `do_tests` scans -- so the
runner and every existing invocation are unchanged.
"""
