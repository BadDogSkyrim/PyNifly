"""Helper routines for tests"""

import sys
import os
import os.path
from pathlib import Path
from collections.abc import Iterable
import logging
import niflytools as NT 
import nifdefs as ND

pynifly_dev_root = os.environ['PYNIFLY_DEV_ROOT']
pynifly_dev_path = os.path.join(pynifly_dev_root, r"pynifly\pynifly")


log = logging.getLogger("pynifly")


PYNIFLY_TEXTURES_SKYRIM = r"C:\Modding\SkyrimSEAssets\00 Vanilla Assets"
PYNIFLY_TEXTURES_FO4 = r"C:\Modding\FalloutAssets\00 FO4 Assets"


def remove_file(fn):
    if os.path.exists(fn):
        os.remove(fn)


def assert_true(val, msg, e=0.0001):
    """Assert the value is truthy."""
    assert val, f"{msg}: Value is {val} should be True"


def assert_equiv(actual, expected, msg, e=0.0001):
    """Assert two values are nearly equal. Values may be scalars, vectors, or matrices."""
    if hasattr(actual, '__getitem__'):
        if hasattr(actual[0], '__getitem__'):
            assert NT.MatNearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"
        else:
            assert NT.VNearEqual(actual[:], expected, epsilon=e), f"Values are equal for {msg}: {actual[:]} != {expected}"
    else:
        assert NT.NearEqual(actual, expected, epsilon=e), f"Values are equal for {msg}: {actual} != {expected}"


def assert_equiv_not(actual, expected, msg, e=0.0001):
    """Assert two values are not nearly equal. Values may be scalars, vectors, or matrices."""
    if hasattr(actual, '__getitem__'):
        if hasattr(actual[0], '__getitem__'):
            assert not NT.MatNearEqual(actual, expected, epsilon=e), f"Values are not equal for {msg}: {actual} != {expected}"
        else:
            assert not NT.VNearEqual(actual[:], expected, epsilon=e), f"Values are not equal for {msg}: {actual} != {expected}"
    else:
        assert not NT.NearEqual(actual, expected, epsilon=e), f"Values are not equal for {msg}: {actual} != {expected}"


    # try:
    #     assert not NT.MatNearEqual(actual, expected, epsilon=e), f"Values are not equal for {msg}: {actual} != {expected}"
    # except AssertionError:
    #     raise
    # except:
    #     try:
    #         assert not NT.VNearEqual(actual[:], expected, epsilon=e), f"Values are not equal for {msg}: {actual[:]} != {expected}"
    #     except AssertionError:
    #         raise
    #     except:
    #         assert not NT.NearEqual(actual, expected, epsilon=e), f"Values are not equal for {msg}: {actual} != {expected}"


def assert_patheq(actual, expected, msg):
    a = Path(actual)
    b = Path(expected)
    assert a == b, f"Paths are equal for {msg}: {a} != {b}"


def assert_eq(*args):
    """Assert all elements but the last are equal. The last is the message to use."""
    msg = args[-1]
    values = args[0:-1]
    assert values[0:-1] == values[1:], f"{msg} are equal: {values}"
    # assert actual == expected, f"{msg} not the same: {actual} = {expected}"


def assert_eq_nocase(actual, expected, msg):
    """Assert all elements but the last are equal. The last is the message to use."""
    assert actual.lower() == expected.lower(), f"{msg} are equal: {actual} != {expected}"
    # assert actual == expected, f"{msg} not the same: {actual} = {expected}"


def assert_ne(actual, expected, msg):
    """Assert actual is not equal to expected."""
    assert actual != expected, f"Values equal for {msg}: {actual} <> {expected}"


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
    assert len(s1.symmetric_difference(s2)) == 0, f"{msg} not the same: {s1}\nvs\n{s2}"


def assert_samemembers(actual, expected, msg):
    """Assert two lists have the same members, maybe not in the same order."""
    assert_seteq(actual, expected, msg)
    assert len(actual) == len(expected), f"{msg} not the same: {actual} == {expected}"


def assert_exists(objname):
    """Assert an object exists in the blender file."""
    obj = NT.find_object(objname)
    assert obj, f"{objname} exists"
    return obj


def get_property(nif, property_path):
    """ Get a property in a nif file by following the given path.
        property_path = list of names to follow to get to the property.
            The first name is the name of a block in the nif file.
            Each subsequent name is either the name of a property in the previous block,
            or the name of a block contained in the previous block.
        Return = value of the final property, or None if not found.
    """
    current = None
    for i, name in enumerate(property_path):
        if i == 0:
            if name == '[ROOT]':
                current = nif.root
            else:
                assert name in nif.shape_dict, f"Have shape {name}"
                current = nif.shape_dict[name]
        else:
            if name == 'len()':
                current = len(current)
            elif type(current) == dict:
                current = current[name]
            elif hasattr(current, '__getitem__'):
                current = current[int(name)]
            elif name == 'NiAlphaProperty':
                current = current.parent.alpha_property
            elif name == 'BSShaderTextureSet':
                current = current.textures
            elif hasattr(current, 'sequences') and current.sequences and 'sequences' == name:
                current = current.sequences
            elif name.startswith('ShaderFlags2'):
                current = 1 if (current & ND.ShaderFlags2[name[13:]]) else 0
            elif name.startswith('properties.'):
                current = getattr(current.properties, name[11:])
            elif hasattr(current, 'shader') and current.shader and current.shader.blockname == name:
                current = current.shader
            elif hasattr(current, 'controller') and current.controller and current.controller.blockname == name:
                current = current.controller
            elif hasattr(current, 'interpolator') and current.interpolator and current.interpolator.blockname == name:
                current = current.interpolator
            elif hasattr(current, 'data') and current.data and current.data.blockname == name:
                current = current.data
            elif hasattr(current, 'object_palette') and current.object_palette and current.object_palette.blockname == name:
                current = current.object_palette
            elif hasattr(current, 'text_key_data') and current.text_key_data and current.text_key_data.blockname == name:
                current = current.text_key_data
            elif hasattr(current, 'target') and current.target and current.target.blockname == name:
                current = current.target
            elif hasattr(current, name):
                current = getattr(current, name)
            elif hasattr(current.properties, name):
                current = getattr(current.properties, name)
            else:
                raise AssertionError(f"Have property {name} in {'/'.join(property_path[0:i])} in {nif.filepath}")
            
    return current


def assert_property(nif, property_path, expected_value):
    """Assert a property in a nif file has the expected value."""
    v = get_property(nif, property_path)
    if type(v).__name__ in ["float", "c_float_Array_2", "c_float_Array_3", "c_float_Array_4"]:
        assert_equiv(v, expected_value, "/".join(property_path))
    else:
        assert_eq(v, expected_value, "/".join(property_path))