"""
Wrapper around nifly to provide python-friendly access to nifs

Check the first test to see basic functionality exercised.
"""

# The block classes live in pyn/blocks, one module per family. This module re-exports
# everything they define, so `from pyn.pynifly import X` and `pynifly.X` keep working.

import os
from enum import Enum
import re
import logging
from ctypes import *
from typing import ValuesView, List
from collections.abc import MutableMapping
import xml.etree.ElementTree as xml
from pathlib import Path
from .niflytools import *
from .nifdefs import *
from .niflydll import nifly, nifly_path
from .nifconstants import BSXFlagsValues, HAVOC_SCALE_FACTOR, game_traits
import importlib as _importlib
from .blocks import (base as _base, collision as _collision, nodes as _nodes, anim as _anim,
                     extradata as _extradata, shaders as _shaders, shapes as _shapes,
                     niffile as _niffile)

# Reloading this module (the Blender test harness does, to pick up edits) rebuilds the
# block families too, in this order: each family's classes derive from the ones before
# it, so any other order would leave classes built on stale bases.
if '_FAMILIES' in globals():
    for _m in _FAMILIES:
        _importlib.reload(_m)
_FAMILIES = (_base, _collision, _nodes, _anim, _extradata, _shaders, _shapes, _niffile)

from .blocks.base import *
from .blocks.collision import *
from .blocks.nodes import *
from .blocks.anim import *
from .blocks.extradata import *
from .blocks.shaders import *
from .blocks.shapes import *
from .blocks.niffile import *
from .blocks.shapes import _TRI_16BIT_BLOCKTYPES
from .blocks.shapes import _UNIT_SCALE_MIN_SAMPLES
from .blocks.shapes import _UNIT_SCALE_TOLERANCE
from .blocks.shapes import _havok_metres_or_one
del annotations  # noqa: F821 -- the families' __future__ import, not an export


# Set up logging
log = logging.getLogger("pynifly")


NiObject.register_subclasses()
