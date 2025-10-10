"""
Check any of our test NIFs for correctness.
"""

from pathlib import Path
from pynifly import NifFile
from nifdefs import EffectShaderControlledVariable, LightingShaderControlledVariable, NiKeyType
import test_tools as TT


def CheckNif_voidshade(nif:NifFile):
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'Emissive_Mult'], 1.7)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'Emissive_Color'], [0.8128, 0.9898, 0.5601, 0.0])
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'Shader_Flags_2', 'ShaderFlags2.VERTEX_COLORS'], 1)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'NiAlphaProperty', 'flags'], 4333)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'flags'], 72)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'frequency'], 1.0)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'stopTime'], 16.0)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'controlledVariable'], LightingShaderControlledVariable.V_Offset)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'properties.keys', 'interpolation'], NiKeyType.LINEAR_KEY)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', 'len()'], 2)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '0', 'time'], 0.0)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '0', 'value'], 1.0)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'time'], 16.0)
    TT.assert_property(nif, ['head', 'BSLightingShaderProperty', 'BSLightingShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'value'], 0.0)


def Check_daedriccuirass(nif:NifFile):
    """Check the daedric cuirass nif file for correctness."""
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'flags'], 72)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'controlledVariable'], EffectShaderControlledVariable.V_Offset)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'NiFloatInterpolator', 'NiFloatData', 'properties.keys', 'interpolation'], NiKeyType.QUADRATIC_KEY)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'NiFloatInterpolator', 'NiFloatData', 'keys', 'len()'], 3)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'time'], 3.3333)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'controller', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'backward'], -1)


test_files = {
    "voidshade_1.nif": CheckNif_voidshade,
    "daedriccuirass_1.nif": Check_daedriccuirass,
}

def CheckNif(nif, source=None):
    if source:
        p = Path(source)
    else:
        p = Path(nif.filepath)
    if p.name in test_files:
        test_files[p.name](nif)
    else:
        raise ValueError(f"No test defined for {p.name}")