import struct
from ctypes import Structure, c_bool, c_char, c_float, c_uint8, c_uint32
import logging

class MaterialFile(Structure):
    """
    Common elements and bhavior for all materials files.
    """
    log = logging.getLogger("pynifly")
    # Class variables overridden by sublclasses.
    _fields_ = []
    _defaults_ = []

    def __init__(self, filepath=None, logger=None):
        if logger: MaterialFile.log = logger
        super().__init__(**self._defaults_)
        self.textures = {}
        if filepath: self.read(filepath)

    @classmethod
    def logError(cls, msg):
        if MaterialFile.log:
            MaterialFile.log.error(msg)
    
    @classmethod
    def logWarning(cls, msg):
        if MaterialFile.log:
            MaterialFile.log.warning(msg)
    
    def read_field(self, fieldname, ftype):
        """Read a single field from the file."""
        try:
            if '_Array_' in ftype.__name__:
                if ftype._type_._type_ == 'c':
                    pat = "<" + str(ftype._length_) + 's'
                    s = struct.Struct(pat)
                    buf = self.sourcefile.read(s.size)
                    v = s.unpack(buf)
                    self.__setattr__(fieldname, v[0])
                else:
                    pat = "<" + str(ftype._type_._type_ *  ftype._length_)
                    s = struct.Struct(pat)
                    buf = self.sourcefile.read(s.size)
                    v = s.unpack(buf)
                    self.__setattr__(fieldname, v)
            else:
                pat = ("<" + ftype._type_)
                s = struct.Struct(pat)
                buf = self.sourcefile.read(s.size)
                v = s.unpack(buf)
                self.__setattr__(fieldname, v[0])
        except:
            # Maybe hit EOF
            pass

    def read_to(self, lastfield):
        """Read all fields up to and including 'lastfield'."""
        for fieldname, ftype in self.flditer:
            self.read_field(fieldname, ftype)
            if fieldname == lastfield:
                break

    def skip_to(self, lastfield):
        """Skip the iterator over fields up to and including 'lastfield'."""
        for fieldname, ftype in self.flditer:
            if fieldname == lastfield:
                break

    def read_if(self, lastfield, condition):
        if condition:
            self.read_to(lastfield)
        else:
            self.skip_to(lastfield)

    def read_text(self, fieldname, condition=True):
        if condition:
            n = struct.unpack('<I', self.sourcefile.read(4))[0]
            t = self.sourcefile.read(n).decode().rstrip('\x00')
            if t:
                self.textures[fieldname] = t

    def _read(self, f):
        """Read common fields from the given file."""
        self.sourcefile = f
        self.flditer = (fld for fld in self._fields_)
        self.read_to('refractionPower')
        self.read_if('environmentMappingMaskScale', self.version < 10)
        self.read_if('depthBias', self.version >= 10)
        self.read_to('grayscaleToPaletteColor')
        self.read_if('maskWrites', self.version > 6)

    def read(self, filename):
        """
        Read the initial fields common to all subclasses.
        """
        try:
            with open(filename, 'rb') as f:
                self._read(f)
        except:
            MaterialFile.logWarning(f"Cannot read materials file '{filename}'")

    def extract(self, d):
        for fn, t in self._fields_:
            if fn not in ['signature', 'version']:
                if fn in self._defaults_:
                    if '_Array_' in t.__name__:
                        v1 = [x for x in self.__getattribute__(fn)]
                        v2 = [x for x in self._defaults_[fn]]
                        if v1 != v2:
                            d[fn] = repr(v1)
                    elif self.__getattribute__(fn) != self._defaults_[fn]:
                        d[fn] = self.__getattribute__(fn)

    @classmethod
    def Open(cls, filepath, logger=None):
        """
        Open the materials file at 'filepath'. Use the signature in the path to decide
        what type of materials file it is.
        """
        if logger: cls.log = logger
        m = None
        try:
            sig = ''
            with open(filepath, 'rb') as f:
                sig = struct.unpack('<4s', f.read(4))[0]
                f.close()
            if sig == b'BGSM':
                m = BGSMaterial(filepath)
            elif sig == b'BGEM':
                m = BGEMaterial(filepath)
            else:
                cls.logError(f"Not a known materials file: {filepath}")
        except:
            cls.logWarning(f"Cannot read materials file '{filepath}'")
        return m


class BGSMaterial(MaterialFile):
    _fields_ = [
        ('signature', c_char*4),
        ('version', c_uint32),
        ('tileFlags', c_uint32), 
        ('UV_Offset_U', c_float), 
        ('UV_Offset_V', c_float), 
        ('UV_Scale_U', c_float), 
        ('UV_Scale_V', c_float), 
        ('Alpha', c_float), 
        ('alphblend0', c_uint8), 
        ('alphblend1', c_uint32), 
        ('alphblend2', c_uint32), 
        ('alphatestref', c_uint8), 
        ('alphatest', c_bool),
        ('zbufferwrite', c_bool), 
        ('zbuffertest', c_bool),
        ('screenSpaceReflections', c_bool), 
        ('wetnessScreenSpaceReflections', c_bool),
        ('decal', c_bool), 
        ('twoSided', c_bool), 
        ('decalNoFade', c_bool), 
        ('nonOccluder', c_bool),
        ('refraction', c_bool), 
        ('refractionFalloff', c_bool), 
        ('refractionPower', c_float),
        ('environmentMapping', c_bool), 
        ('environmentMappingMaskScale', c_float),
        ('depthBias', c_bool),
        ('grayscaleToPaletteColor', c_bool),
        ('maskWrites', c_uint8),
        ('enableEditorAlphaRef', c_bool),
        ('translucency', c_bool), 
        ('translucencyThickObject', c_bool), 
        ('translucencyMixAlbedoWithSubsurfaceColor', c_bool), 
        ('translucencySubsurfaceColor', c_uint32*3), 
        ('translucencyTransmissiveScale', c_float), 
        ('translucencyTurbulence', c_float),
        ('rimLighting', c_bool), 
        ('rimPower', c_float), 
        ('backlightPower', c_float), 
        ('subsurfaceLighting', c_bool),
        ('subsurfaceRolloff', c_float),
        ('specularEnabled', c_bool), 
        ('specularColor', c_float*3),
        ('specularMult', c_float),
        ('smoothness', c_float),
        ('fresnelPower', c_float), 
        ('wetnessSpecScale', c_float),
        ('wetnessSpecPower', c_float), 
        ('wetnessMinVar', c_float),
        ('wetnessEnvmapScale', c_float),
        ('wetnessFresnelPower', c_float),
        ('wetnessMetalness', c_float),
        ('pbr', c_bool),
        ('customPorosity', c_bool),
        ('porosityValue', c_float),
        ('anisoLighting', c_bool),
        ('emitEnabled', c_bool), 
        ('emittanceColor', c_uint32*3), 
        ('emittanceMult', c_float), 
        ('modelSpaceNormals', c_bool), 
        ('externalEmittance', c_bool),
        ('lumEmittance', c_float),
        ('useAdaptativeEmissive', c_bool), 
        ('adaptativeEmissive_ExposureOffset', c_float),
        ('adaptativeEmissive_FinalExposureMin', c_float), 
        ('adaptativeEmissive_FinalExposureMax', c_float),
        ('backLighting', c_bool),
        ('receiveShadows', c_bool), 
        ('hideSecret', c_bool), 
        ('castShadows', c_bool), 
        ('dissolveFade', c_bool),
        ('assumeShadowmask', c_bool), 
        ('glowmap', c_bool),
        ('environmentMappingWindow', c_bool),
        ('environmentMappingEye', c_bool),
        ('hair', c_bool), 
        ('hairTintColor', c_uint32*3), 
        ('tree', c_bool), 
        ('facegen', c_bool), 
        ('skinTint', c_bool), 
        ('tessellate', c_bool),
        ('displacementTextureBias', c_float), 
        ('displacementTextureScale', c_float),
        ('tessellationPnScale', c_float), 
        ('tessellationBaseFactor', c_float), 
        ('tessellationFadeDistance', c_float),
        ('grayscaleToPaletteScale',c_float),
        ('skewSpecularAlpha', c_bool),
        ('terrain', c_bool),
        ('unkInt1', c_uint32),
        ('terrainThresholdFalloff', c_float), 
        ('terrainTilingDistance', c_float), 
        ('terrainRotationAngle', c_float),
        ]
    _defaults_ = {
        'signature': b'BGSM', 
        'version': 2,
        'tileFlags': 3,
        'UV_Scale_U': 1.0,
        'UV_Scale_V': 1.0,
        'Alpha': 1.0,
        'alphatestref': 128,
        'zbufferwrite': 1,
        'zbuffertest': 1,
        'environmentMappingMaskScale': 1.0,
        'translucencyTransmissiveScale': 1.0,
        'rimPower': 2.0,
        'subsurfaceRolloff': 0.3,
        #'specularColor': type(BGSMaterial.specularColor)(0xFF, 0xFF, 0xFF, 0xFF),
        'smoothness': 1.0,
        'fresnelPower': 5.0,
        'wetnessSpecScale': -1.0,
        'wetnessSpecPower': -1.0,
        'wetnessMinVar': -1.0,
        'wetnessEnvmapScale': -1.0,
        'wetnessMetalness': -1.0,
        #'emittanceColor': [0xFF, 0xFF, 0xFF, 0xFF],
        'emittanceMult': 1.0,
        'grayscaleToPaletteScale': 1.0,
        }        
    
    def _read(self, f):
        super()._read(f)
        self.read_text('Diffuse')
        self.read_text('Normal')
        self.read_text('Specular')
        self.read_text('Greyscale')
        self.read_text('Glow', condition=(self.version > 2))
        self.read_text('Wrinkles', condition=(self.version > 2))
        self.read_text('Specular', condition=(self.version > 2))
        self.read_text('Lighting', condition=(self.version > 2))
        self.read_text('Flow', condition=(self.version > 2))
        self.read_text('DistanceFieldAlpha', condition=(self.version > 17))
        self.read_text('EnvMap', condition=(self.version <= 2))
        self.read_text('Glow', condition=(self.version <= 2))
        self.read_text('InnerLayer', condition=(self.version <= 2))
        self.read_text('Wrinkles', condition=(self.version <= 2))
        self.read_text('Height', condition=(self.version <= 2))
        self.read_to('enableEditorAlphaRef')
        self.read_if('translucency', self.version >= 8)
        self.read_if('translucencyThickObject', self.version >= 8)
        self.read_if('translucencyMixAlbedoWithSubsurfaceColor', self.version >= 8)
        self.read_if('translucencySubsurfaceColor', self.version >= 8)
        self.read_if('translucencyTransmissiveScale', self.version >= 8)
        self.read_if('translucencyTurbulence', self.version >= 8)
        self.read_if('rimLighting', self.version < 8)
        self.read_if('rimPower', self.version < 8)
        self.read_if('backlightPower', self.version < 8)
        self.read_if('subsurfaceLighting', self.version < 8)
        self.read_if('subsurfaceRolloff', self.version < 8)
        self.read_to('wetnessMinVar')
        self.read_if('wetnessEnvmapScale', self.version < 10)
        self.read_to('wetnessMetalness')
        self.read_if('pbr', self.version > 2)
        self.read_if('customPorosity', self.version >= 9)
        self.read_if('porosityValue', self.version >= 9)
        self.read_text('RootMaterialPath')
        self.read_to('emitEnabled')
        self.read_if('emittanceColor', self.emitEnabled)
        self.read_to('externalEmittance')
        self.read_if('lumEmittance', self.version >= 12)
        self.read_if('useAdaptativeEmissive', self.version >= 13)
        self.read_if('adaptativeEmissive_ExposureOffset', self.version >= 13)
        self.read_if('adaptativeEmissive_FinalExposureMin', self.version >= 13)
        self.read_if('adaptativeEmissive_FinalExposureMax', self.version >= 13)
        self.read_if('backLighting', self.version < 8)
        self.read_to('glowmap')
        self.read_if('environmentMappingWindow', self.version < 7)
        self.read_if('environmentMappingEye', self.version < 7)
        self.read_to('tessellate')
        self.read_if('displacementTextureBias', self.version < 3)
        self.read_if('displacementTextureScale', self.version < 3)
        self.read_if('tessellationPnScale', self.version < 3)
        self.read_if('tessellationBaseFactor', self.version < 3)
        self.read_if('tessellationFadeDistance', self.version < 3)
        self.read_to('grayscaleToPaletteScale')
        self.read_if('skewSpecularAlpha', self.version >= 1)
        self.read_if('terrain', self.version >= 3)
        if self.version >= 3:
            if self.terrain:
                self.read_if('unkInt1', self.version == 3)
            self.read_to('terrainRotationAngle')


class BGEMaterial(MaterialFile):
    _fields_ = [
        ('signature', c_char*4),
        ('version', c_uint32),
        ('tileFlags', c_uint32), 
        ('UV_Offset_U', c_float), 
        ('UV_Offset_V', c_float), 
        ('UV_Scale_U', c_float), 
        ('UV_Scale_V', c_float), 
        ('Alpha', c_float), 
        ('alphblend0', c_uint8), 
        ('alphblend1', c_uint32), 
        ('alphblend2', c_uint32), 
        ('alphatestref', c_uint8), 
        ('alphatest', c_bool),
        ('zbufferwrite', c_bool), 
        ('zbuffertest', c_bool),
        ('screenSpaceReflections', c_bool), 
        ('wetnessScreenSpaceReflections', c_bool),
        ('decal', c_bool), 
        ('twoSided', c_bool), 
        ('decalNoFade', c_bool), 
        ('nonOccluder', c_bool),
        ('refraction', c_bool), 
        ('refractionFalloff', c_bool), 
        ('refractionPower', c_float),
        ('environmentMapping', c_bool), 
        ('environmentMappingMaskScale', c_float),
        ('depthBias', c_bool),
        ('grayscaleToPaletteColor', c_bool),
        ('maskWrites', c_uint8),
        ('bloodEnabled', c_bool),
        ('effectLightingEnabled', c_bool), 
        ('falloffEnabled', c_bool), 
        ('falloffColorEnabled', c_bool), 
        ('grayscaleToPaletteAlpha', c_bool), 
        ('softEnabled', c_bool), 
        ('baseColor', c_uint32*3),
        ('baseColorScale', c_float),
        ('falloffStartAngle', c_float), 
        ('falloffStopAngle', c_float), 
        ('falloffStartOpacity', c_float), 
        ('falloffStopOpacity', c_float), 
        ('lightingInfluence', c_float), 
        ('envmapMinLOD', c_uint8), 
        ('softDepth', c_float),
        ('emittanceColor', c_uint32*3),
        ('adaptativeEmissive_ExposureOffset', c_float),
        ('adaptativeEmissive_FinalExposureMin', c_float),
        ('adaptativeEmissive_FinalExposureMax', c_float),
        ('glowmap', c_bool),
        ('effectPbrSpecular', c_bool),
        ]
    _defaults_ = {
        'signature': b'BGSM', 
        'version': 2,
        'tileFlags': 3,
        'UV_Scale_U': 1.0,
        'UV_Scale_V': 1.0,
        'Alpha': 1.0,
        'alphatestref': 128,
        'zbufferwrite': 1,
        'zbuffertest': 1,
        'environmentMappingMaskScale': 1.0,
        'translucencyTransmissiveScale': 1.0,
        'rimPower': 2.0,
        'subsurfaceRolloff': 0.3,
        #'specularColor': type(BGSMaterial.specularColor)(0xFF, 0xFF, 0xFF, 0xFF),
        'smoothness': 1.0,
        'fresnelPower': 5.0,
        'wetnessSpecScale': -1.0,
        'wetnessSpecPower': -1.0,
        'wetnessMinVar': -1.0,
        'wetnessEnvmapScale': -1.0,
        'wetnessMetalness': -1.0,
        #'emittanceColor': [0xFF, 0xFF, 0xFF, 0xFF],
        'emittanceMult': 1.0,
        'grayscaleToPaletteScale': 1.0,
        'envMapMaskScale': 1.0,
        'baseColorScale': 1.0
        }        
    
    def _read(self, f):
        super()._read(f)
        self.read_text('Diffuse')
        self.read_text('Greyscale')
        self.read_text('EnvMap')
        self.read_text('Normal')
        self.read_text('EnvMapMask')
        if self.version >= 11:
            self.read_text('Specular')
            self.read_text('Lighting')
            self.read_text('Glow')
        if self.version >= 10:
            self.read_to('environmentMappingMaskScale')
        self.read_to('SoftDepth')
        if self.version >= 11:
            self.read_to('EmittanceColor')
        if self.version >= 15:
            self.read_to('AdaptativeEmissive_FinalExposureMax')
        if self.version >= 16:
            self.read_to('glowmap')
        if self.version >= 20:
            self.read_to('EffectPbrSpecular')


class TestModule:
    @property
    def all_tests(self):
        return [k for k in TestModule.__dict__.keys() if k.startswith('TEST_')]

    def execute_test(self, t):
        print(f"\n------------- {t} -------------")
        the_test = TestModule.__dict__[t]
        print(the_test.__doc__)
        the_test()
        print(f"------------- done")

    def run(self, start=None, test=None):
        print("""\n
=====================================================================
======================= Running tests =======================
=====================================================================

""")
        if test:
            self.execute_test(test)
        else:
            doit = (start is None) 
            for name in self.all_tests:
                if name == start: doit = True
                if doit:
                    self.execute_test(name)

        print("""

============================================================================
======================= TESTS COMPLETED SUCCESSFULLY =======================
============================================================================
""")
    
    # ----------------------------------------------------------------------

    def TEST_READ_BGSM():
        testfile = r"tests\FO4\Materials\actors\Character\BaseHumanMale\test.bgsm"
        m = MaterialFile.Open(testfile)
        assert m.signature.decode() == "BGSM", f"Read signature: {m.signature.decode()}"
        assert m.version == 2, f"Read version: {m.version}"
        assert m.textures['Diffuse'] == r"Actors/Character/BaseHumanMale/BaseMaleHead_d.dds", \
            f"Have correct diffuse texture: {m.textures['Diffuse']}"
        assert m.specularColor[:] == [1.0, 0.0, 0.0], f"Have correct specular color: {m.specularColor[:]}"
        assert m.emitEnabled, f"Emittance enabled"
        assert m.castShadows, f"castShadows correct"
        assert m.grayscaleToPaletteScale == 1.5, f"grayscaleToPaletteScale is correct: {m.grayscaleToPaletteScale}"

        mdict = {}
        m.extract(mdict)
        print(mdict)

    def TEST_READ_BGEM():
        testfile = r"tests\FO4\Materials\Armor\FlightHelmet\glasstest.BGEM"
        m = MaterialFile.Open(testfile)
        assert m.signature.decode() == "BGEM", f"Read signature: {m.signature.decode()}"
        assert m.version == 2, f"Read version: {m.version}"
        assert m.textures['Diffuse'] == r"Armor/FlightHelmet/Helmet_03_d.dds", \
            f"Have correct Diffuse texture: {m.textures['Diffuse']}"
        assert m.environmentMappingMaskScale == 1.5, "environmentMappingMaskScale is correct: {m.environmentMappingMaskScale}"
        assert m.bloodEnabled, "bloodEnabled is enabled."
        assert m.falloffEnabled, "Falloff is enabled."
        assert m.lightingInfluence == 0.75, f"have correct lightingInfluence"
        assert m.envmapMinLOD == 4, f"have correct envmapMinLOD"

        mdict = {}
        m.extract(mdict)
        print(mdict)

    # ----------------------------------------------------------------------

if __name__ == "__main__":
    tester = TestModule()
    tester.run()