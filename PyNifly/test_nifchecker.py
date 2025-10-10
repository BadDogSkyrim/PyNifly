"""
Check any of our test NIFs for correctness.
"""

from pathlib import Path
from pynifly import NifFile
from nifdefs import EffectShaderControlledVariable, LightingShaderControlledVariable, NiKeyType
from niflytools import NearEqual, VNearEqual, MatNearEqual
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
    TT.assert_property(nif, ['TorsoLow:0', 'BSLightingShaderProperty', 'Emissive_Mult'], 0.62)
    TT.assert_property(nif, ['TorsoLow:0', 'BSLightingShaderProperty', 'BSShaderTextureSet', 'EnvMap'], r'textures\cubemaps\Ore_Ebony_e.dds')
    TT.assert_property(nif, ['TorsoLow:0', 'BSLightingShaderProperty', 'BSShaderTextureSet', 'EnvMask'], r'textures\armor\daedric\DaedricArmor_m.dds')
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'UV_Offset_U'], 0.0)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'UV_Offset_V'], 1.0)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'UV_Scale_U'], 10.0)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'UV_Scale_V'], 10.0)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'Shader_Flags_2', 'ShaderFlags2.VERTEX_COLORS'], 1)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'NiAlphaProperty', 'flags'], 4333)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'flags'], 72)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'frequency'], 1.0)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'stopTime'], 33.3333)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'controlledVariable'], EffectShaderControlledVariable.V_Offset)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'properties.keys', 'interpolation'], NiKeyType.QUADRATIC_KEY)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', 'len()'], 3)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'time'], 3.3333)
    TT.assert_property(nif, ['MaleTorsoGlow', 'BSEffectShaderProperty', 'BSEffectShaderPropertyFloatController', 'NiFloatInterpolator', 'NiFloatData', 'keys', '1', 'backward'], -1)


def Check_malehead(nif:NifFile):
    """Check the head """
    assert nif.shapes[0].parent.name == nif.rootName, f"Head parented to root"

    # Transforms
    TT.assert_property(nif, ['MaleHeadIMF', 'transform', 'translation', '2'], 120.343582)
    assert int(nif.shapes[0].global_to_skin.translation[2]) == -120, \
        f"Shape global-to-skin not written correctly, found {nif.shapes[0].global_to_skin.translation[2]}"
    
    # node-to-global transform combines all the transforms to show node's position
    # in space. Since this nif doesn't contain bone relationships, that's just
    # the transform on the bone.
    mat = nif.get_node_xform_to_global("NPC Spine2 [Spn2]")
    assert NearEqual(mat.translation[2], 91.2488), f"Error: Translation should not be 0, found {mat.translation[2]}"

    # If the bone isn't in the nif, the node-to-global is retrieved from
    # the reference skeleton.
    mat2 = nif.get_node_xform_to_global("NPC L Forearm [LLar]")
    assert NearEqual(mat2.translation[2], 85.7311), f"Error: Translation should not be 0, found {mat2.translation[2]}"

    # Partitions
    assert len(nif.shapes[0].partitions) == 3, "Have all skyrim partitions"
    assert set([p.id for p in nif.shapes[0].partitions]) == set([130, 143, 230]), "Have all head parts"
    assert (nif.shapes[0].partitions[0].flags and 1) == 1, "First partition has start-net-boneset set"

    # Partition tri list matches tris 1:1, so has same as number of tris. Refers 
    # to the partitions by index into the partitioin list.
    assert len(nif.shapes[0].partition_tris) == 1694
    assert max(nif.shapes[0].partition_tris) < len(nif.shapes[0].partitions), f"tri index out of range"


test_files = {
    ("SkyrimSE", "voidshade_1.nif"): CheckNif_voidshade,
    ("SkyrimSE","daedriccuirass_1.nif"): Check_daedriccuirass,
    ("Skyrim", "malehead.nif"): Check_malehead,
}

def CheckNif(nif, source=None):
    if source:
        p = Path(source)
    else:
        p = Path(nif.filepath)
    k = (p.parts[p.parts.index('tests')+1], p.name)
    if k in test_files:
        test_files[k](nif)
    else:
        raise ValueError(f"No test defined for {p.name}")