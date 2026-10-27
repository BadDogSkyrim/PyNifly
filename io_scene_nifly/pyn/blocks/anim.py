"""Animation blocks: key data, interpolators, controllers, sequences and the controller
manager's object palette."""

from __future__ import annotations

import os
from enum import Enum
import re
import logging
from ctypes import *
from typing import ValuesView, List
from collections.abc import MutableMapping
import xml.etree.ElementTree as xml
from pathlib import Path
from ..niflytools import *
from ..nifdefs import *
from ..niflydll import nifly, nifly_path
from ..nifconstants import BSXFlagsValues, HAVOC_SCALE_FACTOR, game_traits
from .base import NiObject


log = logging.getLogger("pynifly")


class NiKeyFrameData(NiObject):
    pass


class LinearScalarKey:
    def __init__(self, buf:NiAnimKeyLinearBuf=None):
        if buf:
            self.time = buf.time
            self.value = buf.value
        self.addKey = nifly.addAnimKeyLinear

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)
    
    def __str__(self): 
        return f"<LinearScalarKey>(time={self.time}, value={self.value:f})"

    def getbuf(self):
        buf = NiAnimKeyLinearBuf()
        buf.time = self.time
        buf.value = self.value
        return buf


class LinearVectorKey:
    def __init__(self, buf):
        self.time = buf.time
        self.value = [buf.value[0], buf.value[1], buf.value[2]]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)

    def __str__(self): 
        return f"<LinearVectorKey>(time={self.time}, value=[{self.value[0]:f}, {self.value[1]:f}, {self.value[2]:f}])"


class LinearQuatKey:
    def __init__(self, buf):
        self.time = buf.time
        self.value = [buf.value[0], buf.value[1], buf.value[2], buf.value[3]]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value)

    def __str__(self): 
        return f"<LinearQuatKey>(time={self.time}, value=[{self.value[0]:f}, {self.value[1]:f}, {self.value[2]:f}, {self.value[3]:f}])"


class QuadScalarKey:

    def __init__(self, buf:NiAnimKeyFloatBuf=None):
        if buf:
            self.time = buf.time
            self.value = buf.value
            self.forward = buf.forward
            self.backward = buf.backward
        self.addKey = nifly.addAnimKeyQuadFloat

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value) \
            and VNearEqual(self.forward, other.forward) \
            and VNearEqual(self.backward, other.backward) 

    def __str__(self): 
        return f"<QuadScalarKey>(time={self.time}, value={self.value[:]}, forward={self.forward[:]}, backward={self.backward[:]})"
    
    def getbuf(self):
        buf = NiAnimKeyFloatBuf()
        buf.time = self.time
        buf.value = self.value
        buf.forward = self.forward
        buf.backward = self.backward
        return buf


class QuadVectorKey:
    time = 0.0
    value = []
    forward = 0.0
    backward = 0.0

    def __init__(self, buf:NiAnimKeyQuadTransBuf):
        self.time = buf.time
        self.value = buf.value[:]
        self.forward = buf.forward[:]
        self.backward = buf.backward[:]

    def __eq__(self, other):
        return NearEqual(self.time, other.time) \
            and VNearEqual(self.value, other.value) \
            and VNearEqual(self.forward, other.forward) \
            and VNearEqual(self.backward, other.backward) 

    def __str__(self): 
        return f"<QuadVectorKey>(time={self.time}, value={self.value[:]}, forward={self.forward[:]}, backward={self.backward[:]})"


class NiFloatData(NiObject):
    buffer_type = PynBufferTypes.NiFloatDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None, keys=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        # self.keys = keys
        if self._handle == None and self.id == NODEID_NONE:
            self.id = nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            if keys:
                for k in keys:
                    buf = k.getbuf()
                    k.addKey(self.file._handle, self.id, buf)
            self._handle = nifly.getNodeByID(self.file._handle, self.id)
            if parent: parent.data = self

    @property
    def keys(self):
        _niffile.NifFile.clear_log()
        if self.id == NODEID_NONE: return None
        keys = []
        if self.properties.keys.interpolation in (
                NiKeyType.NO_INTERP, NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY):
            for frame in range(0, self.properties.keys.numKeys):
                # NO_INTERP keys are stored with bare time/value pairs (no tangents),
                # the same layout as LINEAR_KEY, so read them the same way.
                if self.properties.keys.interpolation in (
                        NiKeyType.NO_INTERP, NiKeyType.LINEAR_KEY):
                    buf = NiAnimKeyLinearBuf()
                    if nifly.getAnimKeyLinear(self.file._handle, self.id, frame, buf) != 0:
                        raise Exception(f"Error reading NiFloatDataKey: {_niffile.NifFile.message_log()}")            
                    k = LinearScalarKey(buf)
                else:
                    buf = NiAnimKeyFloatBuf()
                    if nifly.getAnimKeyQuadFloat(self.file._handle, self.id, frame, buf) != 0:
                        raise Exception(f"Error reading NiFloatDataKey: {_niffile.NifFile.message_log()}")            
                    k = QuadScalarKey(buf)
                keys.append(k)
        else:
            raise Exception(f"Unknown controller key type: {self.properties.keys.interpolation}")
        return keys

    def keys_add(self, k):
        """
        Write quadratic float key.
        """
        buf = NiAnimKeyFloatBuf()
        buf.time = k.time
        buf.value = k.value
        buf.forward = k.forward
        buf.backward = k.backward
        nifly.addAnimKeyQuadFloat(self.file._handle, self.id, buf)

    @classmethod
    def getbuf(cls, values=None):
        return NiFloatDataBuf(values)


class NiPosData(NiObject):
    buffer_type = PynBufferTypes.NiPosDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None, keys=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._keys = None

    def _writequadkeys(self, keys):
        """
        Write quadratic float keys.
        keys = list of NiAnimKeyQuadTransBuf 
        """
        for k in keys:
            nifly.addAnimKeyQuadTrans(self.file._handle, self.id, k)

    @property
    def keys(self):
        if (self._keys is None) and (self.id != NODEID_NONE):
            _niffile.NifFile.clear_log()
            if self.properties.keys.interpolation != NiKeyType.QUADRATIC_KEY:
                raise Exception(f"Unknown controller key type: {self.properties.keys.interpolation}")
            self._keys = []
            for frame in range(0, self.properties.keys.numKeys):
                buf = NiAnimKeyQuadTransBuf()
                nifly.getAnimKeyQuadTrans(self.file._handle, self.id, frame, buf) 
                self._keys.append(buf)
        return self._keys


    def add_key(self, key):
        """
        Write one key.
        """
        buf = NiAnimKeyQuadTransBuf()
        buf.time = key.time
        buf.value = key.value
        buf.forward = key.forward
        buf.backward = key.backward
        nifly.addAnimKeyQuadTrans(self.file._handle, self.id, buf)


    @classmethod
    def New(cls, file, interpolation, parent=None):
        p = NiPosDataBuf()
        p.keys.interpolation = interpolation

        pd = file.add_block(None, p, parent)

        return pd


    @classmethod
    def getbuf(cls, values=None):
        return NiPosDataBuf(values)


class NiTransformData(NiKeyFrameData):
    buffer_type = PynBufferTypes.NiTransformDataBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        
        self.xrotations = []
        self.yrotations = []
        self.zrotations = []
        self.qrotations = []
        self.translations = []
        self.scales = []

        if self.properties.rotationType == NiKeyType.XYZ_ROTATION_KEY:
            self._readxyzrot()
        elif self.properties.rotationType in [NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY]:
            self._readlinrot()

        for frame in range(0, self.properties.translations.numKeys):
            k = None
            if self.properties.translations.interpolation == NiKeyType.LINEAR_KEY:
                buf = NiAnimKeyLinearTransBuf()
                nifly.getAnimKeyLinearTrans(self.file._handle, self.id, frame, buf)
                k = LinearVectorKey(buf)
            elif self.properties.translations.interpolation == NiKeyType.QUADRATIC_KEY:
                buf = NiAnimKeyQuadTransBuf()
                nifly.getAnimKeyQuadTrans(self.file._handle, self.id, frame, buf)
                k = QuadVectorKey(buf)
            else:
                _niffile.NifFile.log.warning(f"Found unknown key type: {self.properties.translations.interpolation}")
            if k: self.translations.append(k)

        # Scale keys are single floats, read through the same per-channel calls as XYZ
        # rotation keys (channel 'S').
        scales = self.properties.scales
        if scales.numKeys:
            if scales.interpolation in (NiKeyType.LINEAR_KEY, NiKeyType.QUADRATIC_KEY):
                self.scales = [self._readrotkey('S', f, scales) for f in range(scales.numKeys)]
            else:
                _niffile.NifFile.log.warning(
                    f"Scale keys of type {NiKeyType(scales.interpolation).name} aren't "
                    f"supported; {scales.numKeys} scale keys in block {self.id} ignored")

    @classmethod
    def getbuf(cls, values=None):
        return NiTransformDataBuf(values)
    
    @classmethod 
    def New(cls, file, 
            rotation_type=NiKeyType.LINEAR_KEY, 
            xyz_rotation_types=(NiKeyType.QUADRATIC_KEY, )*3,
            translate_type=NiKeyType.LINEAR_KEY,
            scale_type=NiKeyType.LINEAR_KEY,
            properties=None,
            parent=None):
        p:NiTransformDataBuf = properties
        if not p:
            p = NiTransformDataBuf()
            p.rotationType = rotation_type
            p.translations.interpolation = translate_type
            p.xRotations.interpolation = xyz_rotation_types[0]
            p.yRotations.interpolation = xyz_rotation_types[1]
            p.zRotations.interpolation = xyz_rotation_types[2]
            p.scales.interpolation = scale_type
        td = file.add_block(None, p, parent)
        return td
    
    def _readlinrot(self):
        """Read keys when the type is LINEAR_KEY or QUADRATIC_KEY. These are time, value
        pairs where the value is a quaternion. 
        """
        for frame in range(0, self.properties.rotationKeyCount):
            buf = NiAnimKeyLinearQuatBuf()
            nifly.getAnimKeyLinearQuat(self.file._handle, self.id, frame, buf)
            k = LinearQuatKey(buf)
            self.qrotations.append(k)

    def _readxyzrot(self):
        """Read keys when the type is XYZ_ROTATION_KEY. X, Y, and Z values are in separate
        lists and each can have a different key type. """
        for d, p, v in [('X', self.properties.xRotations, self.xrotations), 
                        ('Y', self.properties.yRotations, self.yrotations), 
                        ('Z', self.properties.zRotations, self.zrotations)]:
            for f in range(0, p.numKeys):
                k = self._readrotkey(d, f, p)
                v.append(k)

    def _readrotkey(self, d, frame, rots):
        dimension = c_char()
        dimension.value = d.encode('utf-8')
        if rots.interpolation == NiKeyType.QUADRATIC_KEY:
            buf = NiAnimKeyFloatBuf()
            nifly.getAnimKeyQuadXYZ(self.file._handle, self.id, dimension, frame, buf)
            k = QuadScalarKey(buf)
        elif rots.interpolation == NiKeyType.LINEAR_KEY:
            buf = NiAnimKeyLinearBuf()
            nifly.getAnimKeyLinearXYZ(self.file._handle, self.id, dimension, frame, buf)
            k = LinearScalarKey(buf)
        return k

    def add_translation_key(self, time, loc):
        """Add a key that does a translation. Keys must be added in time order."""
        buf = NiAnimKeyLinearTransBuf()
        buf.time = time
        buf.value = loc[:]
        nifly.addAnimKeyLinearTrans(self.file._handle, self.id, buf)

    def add_quad_translation_keys(self, keys):
        """
        Add tranlation keys with quadratic interpolation.
        keys = [NiAnimKeyQuadTransBuf, ...]
        """
        for k in keys:
            nifly.addAnimKeyQuadTrans(self.file._handle, self.id, k)

    def add_qrotation_key(self, time, q):
        """
        Add a key that does a rotation given as a quaternion, linear interpolation. 
        Keys must be added in time order.
        """
        buf = NiAnimKeyLinearQuatBuf()
        buf.time = time
        buf.value = q[:]
        nifly.addAnimKeyLinearQuat(self.file._handle, self.id, buf)

    def add_xyz_rotation_keys(self, dimension, key_list):
        """
        Add XYZ rotation keys.
        key_list = [NiAnimKeyFloatBuf, ...]
        """
        keytype = ''
        if dimension == "X": 
            keytype = self.properties.xRotations.interpolation
        elif dimension == "Y": 
            keytype = self.properties.yRotations.interpolation
        elif dimension == "Z": 
            keytype = self.properties.zRotations.interpolation
        elif dimension == "S": 
            keytype = self.properties.scales.interpolation
        
        d = c_char()
        d.value = dimension.encode('utf-8')
        if keytype == NiKeyType.QUADRATIC_KEY:
            for q in key_list:
                nifly.addAnimKeyQuadXYZ(
                    self.file._handle, self.id, d, byref(q.getbuf()))
        elif keytype in (NiKeyType.LINEAR_KEY, NiKeyType.NO_INTERP):
            # Linear keys are time/value only--no tangents.
            for q in key_list:
                nifly.addAnimKeyLinearXYZ(
                    self.file._handle, self.id, d, byref(q.getbuf()))
        elif key_list:
            # Don't drop keys silently: an empty channel is a broken animation and
            # much harder to spot than a loud failure here.
            raise NotImplementedError(
                f"Cannot write {len(key_list)} '{dimension}' rotation keys of type "
                f"{keytype!r}")


class NiInterpolator(NiObject):
    buffer_type = -1  # Abstract class

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._data = None

    @property
    def data(self):
        if self._data: return self._data
        if self.properties.dataID == NODEID_NONE: return None
        self._data = self.file.read_node(id=self.properties.dataID, parent=self)
        return self._data

    @data.setter
    def data(self, c):
        self._data = c
        self.properties.dataID = c.id

    def _default_import_func(interp, importer, nifnode):
        importer.warn(f"NYI: Import of interpolator {interp.id} {interp}")
    
    import_node = _default_import_func

    @classmethod
    def New(cls, file, data=None, parent=None):
        p = cls.getbuf()
        p.dataID = (data.id if data else NODEID_NONE)
        interp = file.add_block(None, p, parent)
        if data:
            interp._data = data
        return interp


class NiKeyBasedInterpolator(NiInterpolator):
    pass


class NiPathInterpolator(NiKeyBasedInterpolator):
    """Moves its target along a spline path (NiPosData) at a percent-along-path given
    over time (NiFloatData). Recognised so it isn't reported as an unknown block, but not
    read: the DLL has no buffer for it, and path animation isn't imported. Importers
    skip it and say so."""
    buffer_type = -1

    @property
    def data(self):
        return None


class NiTransformInterpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiTransformInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._data = None

    @property
    def rotation(self):
        return self.properties.rotation
        
    @classmethod
    def getbuf(cls, values=None):
        return NiTransformInterpolatorBuf(values)
    
    @classmethod
    def New(cls, file, 
            translation=(0,0,0), rotation=(1,0,0,0), scale=1.0, 
            data_block=None, parent=None):
        p = NiTransformInterpolatorBuf()
        p.translation = translation
        p.rotation = rotation[:]
        p.scale = scale
        p.dataID = data_block.id if data_block else NODEID_NONE
        ti = file.add_block(None, p, parent)
        return ti


class BSRotAccumTransfInterpolator(NiTransformInterpolator):
    pass


class NiFloatInterpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiFloatInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if self.id == NODEID_NONE and file and properties:
            self.id = nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            self._handle = check_msg(nifly.getNodeByID,self.file._handle, self.id)
            if parent: parent.interpolator = self
        self._data = None
        
    @classmethod
    def getbuf(cls, values=None):
        return NiFloatInterpolatorBuf(values)

    @classmethod
    def New(cls, file, data=None, value=None, parent=None):
        p = cls.getbuf()
        p.dataID = (data.id if data else NODEID_NONE)
        p.floatValue = value if value is not None else 0.0
        interp = file.add_block(None, p, parent)
        if data:
            interp._data = data
        return interp


class NiBoolInterpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiBoolInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if self.id == NODEID_NONE and file and properties:
            self.id = nifly.addBlock(
                self.file._handle, 
                None, 
                byref(self.properties), 
                parent.id if parent else NODEID_NONE)
            self._handle = check_msg(
                nifly.getNodeByID, self.file._handle, self.id)
            if parent: parent.interpolator = self
        self._data = None
        
    @classmethod
    def getbuf(cls, values=None):
        return NiBoolInterpolatorBuf(values)

    @property
    def data(self):
        """The NiBoolData of keys, or None when the interpolator just holds its value."""
        if self._data: return self._data
        if self.properties.dataID == NODEID_NONE: return None
        self._data = self.file.read_node(id=self.properties.dataID, parent=self)
        return self._data

    @data.setter
    def data(self, d):
        # The link itself is made in the DLL when the NiBoolData is created under this
        # interpolator (NiBoolData.New); this keeps the cached view in step.
        self._data = d
        self.properties.dataID = d.id

    @classmethod
    def New(cls, file, data=None, value=None, parent=None):
        p = cls.getbuf()
        p.dataID = (data.id if data else NODEID_NONE)
        p.value = int(round(value)) if value is not None else 0
        interp = file.add_block(None, p, parent)
        if data:
            interp._data = data
        return interp


class NiBoolData(NiObject):
    """Keys for a bool interpolator (visibility): time and a 0/1 value each. Read and written
    as linear float keys; the DLL turns the values to and from its bytes."""
    buffer_type = PynBufferTypes.NiBoolDataBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiBoolDataBuf(values)

    @property
    def keys(self):
        keys = []
        for frame in range(self.properties.keys.numKeys):
            buf = NiAnimKeyLinearBuf()
            if nifly.getAnimKeyLinear(self.file._handle, self.id, frame, buf) != 0:
                raise Exception(f"Error reading NiBoolData key: {_niffile.NifFile.message_log()}")
            k = LinearScalarKey(buf)
            k.value = int(round(k.value))
            keys.append(k)
        return keys

    def keys_add(self, time, value):
        buf = NiAnimKeyLinearBuf()
        buf.time = time
        buf.value = float(value)
        nifly.addAnimKeyLinear(self.file._handle, self.id, buf)

    @classmethod
    def New(cls, file, interpolation=NiKeyType.LINEAR_KEY, keys=(), parent=None):
        """A NiBoolData with (time, value) keys; set as `parent`'s data if given."""
        p = cls.getbuf()
        p.keys.interpolation = interpolation
        d = file.add_block(None, p, parent)       # the DLL links it to `parent`
        for t, v in keys:
            d.keys_add(t, v)
        d.properties.keys.numKeys = len(keys)
        if parent is not None:
            parent.data = d
        return d


class NiPoint3Interpolator(NiKeyBasedInterpolator):
    buffer_type = PynBufferTypes.NiPoint3InterpolatorBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiPoint3InterpolatorBuf(values)


class NiBlendInterpolator(NiObject):
    """Abstract class"""
    buffer_type = PynBufferTypes.NiBlendInterpolatorBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        if parent: parent.interpolator = self
        
    @classmethod
    def getbuf(cls, values=None):
        return NiBlendInterpolatorBuf(values)
    
    @classmethod
    def New(cls, file, parent=None):
        p = cls.getbuf()
        intp = file.add_block(None, p, parent)
        return intp
    
    def _default_creator(exporter):
        raise Exception("NYI: Export unknown blend interpolator")
    
    blend_interpolator = _default_creator


class NiBlendBoolInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendBoolInterpolatorBufType

    @property
    def value(self):
        return self.properties.boolValue
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendBoolInterpolatorBufType
        b.boolValue = 2 # Default as found in vanilla nifs
        return b


class NiBlendFloatInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendFloatInterpolatorBufType

    @property
    def value(self):
        return self.properties.floatValue
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendFloatInterpolatorBufType
        return b


class NiBlendPoint3Interpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendPoint3InterpolatorBufType

    @property
    def value(self):
        return self.properties.point3Value[:]
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendPoint3InterpolatorBufType
        return b


class NiBlendTransformInterpolator(NiBlendInterpolator):
    buffer_type = PynBufferTypes.NiBlendTransformInterpolatorBufType

    @property
    def value(self):
        return None
    
    @classmethod
    def getbuf(cls, values=None):
        b = NiBlendInterpolatorBuf(values)
        b.bufType = PynBufferTypes.NiBlendTransformInterpolatorBufType
        return b


class NiTimeController(NiObject):
    """
    Abstract class for time controllers. Keeping the chain of subclasses below because
    we'll likely need them eventually.
    """
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = target
        if parent: parent.controller = self

    @property 
    def next_controller(self):
        if self.properties.nextControllerID == NODEID_NONE:
            return None
        else:
            return self.file.read_node(self.properties.nextControllerID)
        
    @property
    def target(self):
        if self._target: return self._target
        if self.properties.targetID == NODEID_NONE: return None
        self._target = self.file.read_node(id=self.properties.targetID)
        return self._target
    
    @property
    def is_cyclic(self):
        f = TimeControllerFlags()
        f.flags = self.properties.flags
        return f.cycle_type == CycleType.LOOP
    
    def _default_import_func(ctlr, importer, nifnode=None):
        raise Exception(f"NYI: Import of controller {ctlr.id} {ctlr}")
    
    def _default_fcurve_export(exporter, fcurves, target_obj):
        raise Exception(f"NYI: Export of fcurves on {target_obj.name}")
    
    import_node = _default_import_func
    fcurve_exporter = _default_fcurve_export


class NiInterpController(NiTimeController):
    pass


class NiSingleInterpController(NiInterpController):
    buffer_type = PynBufferTypes.NiSingleInterpControllerBufType

    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._target = target
        self._interpolator = interpolator
        
    @property
    def interpolator(self):
        if self._interpolator: return self._interpolator
        if self.properties.interpolatorID == NODEID_NONE: return None
        self._interpolator = self.file.read_node(
            id=self.properties.interpolatorID, parent=self)
        return self._interpolator
    
    @interpolator.setter
    def interpolator(self, c):
        self._interpolator = c
        self.properties.interpolatorID = c.id

    @property
    def target(self):
        if self._target: return self._target
        if self.properties.targetID == NODEID_NONE: return None
        self._target = self.file.read_node(id=self.properties.targetID)
        return self._target

    @classmethod
    def New(cls, file, 
            flags=108, 
            next_controller=None, 
            start_time=sys.float_info.max, stop_time=-sys.float_info.max, 
            frequency=1.0,
            phase=0,
            interpolator=None, 
            target=None, 
            var=0, 
            parent=None):
        p = cls.getbuf()
        p.flags = flags
        p.nextControllerID = (next_controller.id if next_controller else NODEID_NONE)
        p.startTime = start_time
        p.stopTime = stop_time
        p.frequency = frequency
        p.phase = phase
        if hasattr(p, 'controlledVariable'):
            # Only the ShaderProperty subclasses have this field
            p.controlledVariable = var
        if target: p.targetID = (target.id if target else NODEID_NONE)
        if interpolator: p.interpolatorID = (interpolator.id if interpolator else NODEID_NONE)
        c = file.add_block(None, p, parent)
        c._target = target
        c._interpolator = interpolator
        return c


class NiKeyframeController(NiSingleInterpController):
    pass


class NiTransformController(NiKeyframeController):
    buffer_type = PynBufferTypes.NiTransformControllerBufType

    def __init__(self, 
                 handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(
            handle=handle, file=file, id=id, properties=properties, parent=parent,
            target=target, interpolator=interpolator)
        self._target = None
        self._properties = NiTransformControllerBuf()
        check_return(nifly.getBlock, self.file._handle, self.id, byref(self._properties))

    @classmethod
    def getbuf(cls, values=None):
        return NiTransformControllerBuf(values)


class NiMultiTargetTransformController(NiInterpController):
    buffer_type = PynBufferTypes.NiMultiTargetTransformControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        self._properties = NiMultiTargetTransformControllerBuf()
        check_return(nifly.getBlock, self.file._handle, self.id, byref(self._properties))

    @classmethod
    def getbuf(cls, values=None):
        return NiMultiTargetTransformControllerBuf(values)
    
    @classmethod
    def New(cls, file, flags, target, parent=None):
        p = NiMultiTargetTransformControllerBuf()
        p.flags = flags
        p.targetID = target.id
        tc = file.add_block(None, p, parent)
        tc._target = target
        return tc


class NiFloatInterpController(NiSingleInterpController):
    pass


class NiBoolInterpController(NiSingleInterpController):
    pass


class NiVisController(NiSingleInterpController):
    buffer_type = PynBufferTypes.NiVisControllerBufType

    @classmethod
    def getbuf(cls, values=None):
        return NiSingleInterpControllerBuf(
            values=values, buftype=PynBufferTypes.NiVisControllerBufType)


class BSEffectShaderPropertyColorController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyColorControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        if self.id == NODEID_NONE and file and properties: 
            self.id = nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def getbuf(cls, values=None):
        return BSEffectShaderPropertyColorControllerBuf(values)


class BSLightingShaderPropertyColorController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSLightingShaderPropertyColorControllerBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLightingShaderPropertyColorControllerBuf(values)

    @classmethod
    def New(cls, file, flags, target, 
            start_time, stop_time,
            interpolator=None,
            next_controller=None,
            var=LightingShaderControlledColor.SPECULAR,
            parent=None):
        p = BSLightingShaderPropertyColorControllerBuf()
        p.flags = flags
        p.startTime = start_time
        p.stopTime = stop_time
        p.targetID = target.id
        p.nextControllerID = next_controller.id if next_controller else NODEID_NONE
        p.interpolatorID = interpolator.id if interpolator else NODEID_NONE
        p.typeOfControlledColor = var
        tc = file.add_block(None, p, parent)
        return tc


class BSEffectShaderPropertyFloatController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSEffectShaderPropertyFloatControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)
        if self.id == NODEID_NONE and file and properties: 
            self.id = nifly.addBlock(
                file._handle,
                None,
                byref(properties),
                parent.id if parent else None
            )
            if parent: parent.controller = self

    @classmethod
    def getbuf(cls, values=None):
        return BSEffectShaderPropertyFloatControllerBuf(values)


class BSLightingShaderPropertyFloatController(NiFloatInterpController):
    buffer_type = PynBufferTypes.BSLightingShaderPropertyFloatControllerBufType

    @classmethod
    def getbuf(cls, values=None):
        return BSLightingShaderPropertyFloatControllerBuf(values)


class NiAlphaController(NiFloatInterpController):
    pass


class BSNiAlphaPropertyTestRefController(NiAlphaController):
    buffer_type = PynBufferTypes.BSNiAlphaPropertyTestRefControllerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None,
                 target=None, interpolator=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent,
                 target=target, interpolator=interpolator)

    @classmethod
    def getbuf(cls, values=None):
        return BSNiAlphaPropertyTestRefControllerBuf(values)


class ControllerLink:
    buffer_type = PynBufferTypes.NiControllerLinkBufType


    def __init__(self, props:ControllerLinkBuf, parent):
        self.properties = props.copy()
        self.parent = parent
        self._controller = None
        self._nodename = None
        self._controller_type = None
        self._property_type = None
        self._interpolator = None

    @property
    def node_name(self):
        if self._nodename is None: 
            self._nodename = self.parent.file.get_string(self.properties.nodeName)
        return self._nodename
    
    @property
    def controller_type(self):
        if self._controller_type is None: 
            self._controller_type = self.parent.file.get_string(self.properties.ctrlType)
        return self._controller_type
    
    @property
    def property_type(self):
        if self._property_type is None: 
            self._property_type = self.parent.file.get_string(self.properties.propType)
        return self._property_type
    
    @property
    def interpolator(self):
        if self._interpolator: return self._interpolator
        self._interpolator = self.parent.file.read_node(
            id=self.properties.interpolatorID, parent=self.parent)
        return self._interpolator

    @property
    def controller(self):
        if self._controller: return self._controller
        if self.properties.controllerID == NODEID_NONE: return None
        self._controller = self.parent.file.read_node(id=self.properties.controllerID, parent=self)
        return self._controller
    
    @controller.setter
    def controller(self, node):
        self._controller = node
    
    @classmethod
    def New(cls, node_name, controller_type, file, properties=ControllerLinkBuf(), 
            parent=None):
        properties.nodeName = nifly.addString(
            file._handle, node_name.encode('utf-8'))
        properties.ctrlType = nifly.addString(
            file._handle, controller_type.encode('utf-8'))
        parent.add_controlled_block(
            node_name,
            properties.interpolatorID,
        )


class NiSequence(NiObject):
    buffer_type = PynBufferTypes.NiControllerSequenceBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._name = None
        self._controlled_blocks = None

    @property
    def name(self):
        if self._name: return self._name

        self._name = self.file.get_string(self.properties.nameID)

        return self._name
    
    @property
    def controlled_blocks(self):
        if self._controlled_blocks is not None: return self._controlled_blocks
        
        self._controlled_blocks = []
        if self.properties.controlledBlocksCount > 0:
            buf = (ControllerLinkBuf * self.properties.controlledBlocksCount)()
            buf[0].bufSize = sizeof(ControllerLinkBuf) 
            buf[0].bufType = PynBufferTypes.NiControllerLinkBufType
            check_msg(
                nifly.getControlledBlocks,
                self.file._handle, 
                self.id, 
                self.properties.controlledBlocksCount, 
                byref(buf))
            for b in buf:
                self._controlled_blocks.append(ControllerLink(b, self))

        return self._controlled_blocks
    
    @property
    def accum_root_name(self):
        namebuf = (c_char * self.file.max_string_len)()
        check_msg(
            nifly.getString,
            self.file._handle, 
            self.properties.accumRootNameID, 
            self.file.max_string_len, 
            namebuf)
        return namebuf.value.decode('utf-8')

    def add_controlled_block(self,
                             name:str,
                             interpolator=None,
                             controller=None,
                             priority=0,
                             node_name=None,
                             #prop_type=None,
                             controller_type=None,
                             #ctrlr_id=None,
                             #interpolator_id=None,
                             ):
        buf = ControllerLinkBuf()
        buf.interpolatorID = interpolator.id if interpolator else NODEID_NONE
        buf.controllerID = controller.id if controller else NODEID_NONE
        buf.priority = priority
        buf.nodeName = NODEID_NONE
        buf.ctrlType = NODEID_NONE
        buf.ctrlID = NODEID_NONE
        buf.propType = NODEID_NONE
        if node_name is None:
            if name:
                node_name = name
            elif controller:
                if isinstance(controller.target, (_shaders.NiShader, _shaders.NiAlphaProperty,)):
                    node_name = controller.target.parent.name
                else:
                    node_name = controller.target.name
            else:
                node_name = ''
        buf.nodeName = nifly.addString(
            self.file._handle, node_name.encode('utf-8'))

        if controller and not isinstance(controller.target, NiNode): 
            prop_type = controller.target.blockname
            buf.propType = nifly.addString(
                self.file._handle, prop_type.encode('utf-8'))

            if controller_type is None:
                controller_type = controller.blockname

        if controller_type is None: 
            buf.ctrlType = NODEID_NONE
        else:
            buf.ctrlType = nifly.addString(
                self.file._handle, controller_type.encode('utf-8'))

        # Not adding the controller ID or interpoator ID string values because those can
        # change when nifly does cleanup on save. If this turns out to be a problem, we'll
        # have to set them after cleanup.
        buf.interpID = NODEID_NONE
        
        nifly.addBlock(self.file._handle, name.encode('utf-8'), byref(buf), self.id)
        if self._controlled_blocks is None: self._controlled_blocks = []
        self._controlled_blocks.append(ControllerLink(buf, self))

    def _default_import_func(self, importer):
        importer.warn(f"NYI: Import of NiSequence {self.id} {self.name}")
    
    import_node = _default_import_func


class NiControllerSequence(NiSequence):
    buffer_type = PynBufferTypes.NiControllerSequenceBufType
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._text_key_data = None

    @property
    def accumRootName(self):
        namebuf = (c_char * self.file.max_string_len)()
        nifly.getString(
            self.file._handle, 
            self.properties.accumRootNameID, 
            self.file.max_string_len, 
            namebuf)
        return namebuf.value.decode('utf-8')

    @property
    def is_cyclic(self):
        return self.properties.cycleType == 0
    
    @property
    def text_key_data(self) -> _extradata.NiTextKeyExtraData:
        if self._text_key_data is None:
            self._text_key_data = self.file.read_node(
                id=self.properties.textKeyID)
        return self._text_key_data

    @classmethod
    def getbuf(cls, values=None):
        return NiControllerSequenceBuf(values)
    
    @classmethod
    def New(cls, file, name, accum_root_name=None, frequency=1, phase=0,
            start_time=0, stop_time=0, cycle_type=CycleType.CLAMP, weight=1.0,
            text_key_data=None, parent=None, 
            ):
        """
        Create a new controller sequence block.
        """
        p = NiControllerSequenceBuf()
        p.frequency = frequency
        p.phase = phase
        p.startTime = start_time
        p.stopTime = stop_time
        p.cycleType = cycle_type
        p.textKeyID = text_key_data.id if text_key_data else NODEID_NONE
        p.weight = weight

        if parent: p.managerID = parent.id
        if accum_root_name is not None:
            p.accumRootNameID = nifly.addString(
                file._handle, 
                accum_root_name.encode('utf-8'))

        cs = file.add_block(name, p, parent)
        cs._name = name
        if parent: parent.add_sequence(cs)
        return cs


class NiControllerManager(NiTimeController):
    buffer_type = PynBufferTypes.NiControllerManagerBufType

    def __init__(self, handle=None, file=None, id=NODEID_NONE, 
                 properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._properties = NiControllerManagerBuf()
        self._controller_manager_sequences = None
        self._object_palette = None
        check_return(nifly.getBlock,
                     self.file._handle, 
                     self.id, 
                     byref(self._properties))

    @property
    def sequences(self):
        if self._controller_manager_sequences != None:
            return self._controller_manager_sequences
        
        cms_count = nifly.getControllerManagerSequences(
            self.file._handle, self._handle, 0, None)
        cmsids = (c_uint32 * cms_count)()
        check_msg(
            nifly.getControllerManagerSequences,
            self.file._handle, self._handle, cms_count, cmsids)
        
        self._controller_manager_sequences = {}
        for id in cmsids:
            cs = NiControllerSequence(id=id, file=self.file)
            self._controller_manager_sequences[cs.name] = cs

        return self._controller_manager_sequences
    
    def add_sequence(self, seq):
        """
        Add the given controller sequence to the mananger.

        The nif file is not changed. 
        """
        self._controller_manager_sequences[seq.name] = seq

    @property
    def object_palette(self):
        if self._object_palette != None:
            return self._object_palette
        elif self.properties.objectPaletteID == NODEID_NONE:
            return None
        else:
            self._object_palette = self.file.read_node(
                self.properties.objectPaletteID)
            return self._object_palette

    @classmethod
    def getbuf(cls, values=None):
        return NiControllerManagerBuf(values)
    
    @classmethod
    def New(cls, file, flags:TimeControllerFlags, next_controller=None, 
            object_palette=None, parent=None):
        """
        Create a new controller manager block within the target file.
        """
        p = NiControllerManagerBuf()
        p.targetID = parent.id if parent else NODEID_NONE
        p.nextControllerID = next_controller.id if next_controller else NODEID_NONE
        p.flags = flags.flags
        p.objectPaletteID = object_palette.id if object_palette else NODEID_NONE
        cm = file.add_block(None, p, parent)
        cm._controller_manager_sequences = {}
        return cm


class NiDefaultAVObjectPalette(NiObject):
    buffer_type = PynBufferTypes.NiDefaultAVObjectPaletteBufType
    
    def __init__(self, handle=None, file=None, id=NODEID_NONE, properties=None, parent=None):
        super().__init__(handle=handle, file=file, id=id, properties=properties, parent=parent)
        self._objects = None

    @classmethod 
    def getbuf(cls, values=None):
        return NiDefaultAVObjectPaletteBuf(values)
    
    @property
    def objects(self):
        """
        Objects returned as dict {}"object name": object, ...}
        """
        if self._objects is None:
            self._objects = {}
            for i in range(0, self.properties.objCount):
                name = create_string_buffer(256)
                refid = (c_uint32)()
                nifly.getAVObjectPaletteObject(
                    self.file._handle,
                    self.id,
                    i, 
                    256, name,
                    refid
                )
                refnode = self.file.read_node(refid.value)
                self._objects[name.value.decode('utf-8')] = refnode
        return self._objects
    
    def add_object(self, objname, obj):
        if self._objects is None: 
            self._objects = {}
        if objname not in self._objects:
            nifly.addAVObjectPaletteObject(
                self.file._handle,
                self.id,
                objname.encode('utf8'),
                obj.id
            )
            self._objects[objname] = obj
    
    @classmethod
    def New(cls, file, scene=None, objects=None, parent=None):
        p = NiDefaultAVObjectPaletteBuf()
        p.sceneID = scene.id if scene else NODEID_NONE
        objp = file.add_block(None, p, parent)
        for name, obj in (objects or {}).items():
            objp.add_object(name, obj)
        return objp


# Blocks of other families, used inside methods. Imported last: the families
# refer to each other, and by now every class here is defined.
from .base import (check_msg, check_return)  # noqa: E402
from .nodes import (NiNode)  # noqa: E402
from . import extradata as _extradata  # noqa: E402
from . import shaders as _shaders  # noqa: E402
from . import niffile as _niffile  # noqa: E402
