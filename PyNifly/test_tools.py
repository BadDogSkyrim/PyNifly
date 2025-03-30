"""Helper routines for tests"""

import sys
import os
import os.path
import logging
from niflytools import *

pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")


log = logging.getLogger("pynifly")


PYNIFLY_TEXTURES_SKYRIM = r"C:\Modding\SkyrimSE\mods\00 Vanilla Assets"
PYNIFLY_TEXTURES_FO4 = r"C:\Modding\Fallout4\mods\00 FO4 Assets"


def remove_file(fn):
    if os.path.exists(fn):
        os.remove(fn)


def assert_equiv(actual, expected, msg, e=0.0001):
    """Assert two values are nearly equal. Values may be scalars, vectors, or matrices."""
    try:
        assert MatNearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"
    except AssertionError:
        raise
    except:
        try:
            assert VNearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"
        except AssertionError:
            raise
        except:
            assert NearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"


def assert_eq(*args):
    """Assert all elements but the last are equal. The last is the message to use."""
    msg = args[-1]
    values = args[0:-1]
    assert values[0:-1] == values[1:], f"{msg} are equal: {values}"
    # assert actual == expected, f"{msg} not the same: {actual} = {expected}"


def assert_lt(actual, expected, msg, e=0.0001):
    """Assert actual is less than expected."""
    assert actual < expected, f"Values actual less than expected for {msg}: {actual} < {expected}"


def assert_le(actual, expected, msg, e=0.0001):
    """Assert actual is less than expected."""
    assert actual <= expected, f"Values actual less than expected for {msg}: {actual} <= {expected}"


def assert_gt(actual, expected, msg, e=0.0001):
    """Assert actual is greater than expected."""
    assert actual > expected, f"Values actual greater than expected for {msg}: {actual} > {expected}"


def assert_contains(element, collection, message):
    assert element in collection, f"{message} {element} in {collection}"


def assert_seteq(actual, expected, msg):
    """Assert two lists have the same members. Members may be duplicated."""
    if type(actual) == set:
        s1 = actual
    else:
        s1 = set(actual)
    if type(expected) == set:
        s2 = expected
    else:
        s2 = set(expected)
    assert len(s1.symmetric_difference(s2)) == 0, f"{msg} not the same: {s1} vs {s2}"


def assert_samemembers(actual, expected, msg):
    """Assert two lists have the same members, maybe not in the same order."""
    assert_seteq(actual, expected, msg)
    assert len(actual) == len(expected), f"{msg} not the same: {actual} == {expected}"


def assert_exists(objname):
    """Assert an object exists in the blender file."""
    obj = find_object(objname)
    assert obj, f"{objname} exists"
    return obj

