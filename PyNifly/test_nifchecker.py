"""
Check any of our test NIFs for correctness.

assert_property is a convenient shortcut, but it doesn't demonstrate the use of pyNifly as
well. So a lot of the tests use direct function calls.
"""

from pathlib import Path
from pynifly import NifFile
from nifdefs import CycleType, EffectShaderControlledVariable, LightingShaderControlledVariable, \
    NiKeyType, CycleType, ShaderFlags1FO4, ShaderFlags2FO4
from niflytools import NearEqual, VNearEqual, MatNearEqual
import test_tools as TT


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


def Check_noblechest01(nif:NifFile):
    """Check the noblechest01 nif file for correctness."""
    TT.assert_eq(nif.root.controller.__class__.__name__, 'NiControllerManager', "controller class")
    TT.assert_eq(nif.root.controller.properties.flags, 76, "ControllerManager flags")

    # Lid01 is the only node that is actually animated. Vanilla object palette lists all
    # shapes in the nif. Blender export only includes the animated nodes. We think this is
    # ok.
    TT.assert_eq(nif.root.controller.object_palette.__class__.__name__, 'NiDefaultAVObjectPalette', "ObjectPalette class")
    assert len(nif.root.controller.object_palette.objects) in (1, 4), f"Have correct ObjectPalette objects, found {len(nif.root.controller.object_palette.objects)}"
    assert 'Lid01' in nif.root.controller.object_palette.objects, "Have Lid01 in ObjectPalette"
    TT.assert_eq(nif.root.controller.object_palette.objects['Lid01'].flags, 524430, "ObjectPalette Lid01 flags")

    TT.assert_eq(len(nif.root.controller.sequences), 2, "sequences count")
    TT.assert_seteq(set(s for s in nif.root.controller.sequences), {'Close', 'Open'}, "sequences")
    TT.assert_eq(nif.root.controller.sequences['Open'].__class__.__name__, 'NiControllerSequence', "Open sequence class")
    TT.assert_eq(nif.root.controller.sequences['Open'].properties.cycleType, CycleType.CLAMP, "Open sequence cycleType")
    TT.assert_eq(len(nif.root.controller.sequences['Open'].text_key_data.keys), 2, "Open sequence text_key_data keys count")
    TT.assert_eq(nif.root.controller.sequences['Open'].text_key_data.keys[1], (0.5, 'end'), "Open sequence text_key_data key 0")
    TT.assert_eq(len(nif.root.controller.sequences['Open'].controlled_blocks), 1, "Open sequence controlled_blocks count")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].node_name, 'Lid01', "Open sequence controlled_blocks[0] node_name")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].controller.__class__.__name__, 'NiMultiTargetTransformController', "Open sequence controlled_blocks[0] controller class")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].controller.target.id, 0, "Open sequence controlled_blocks[0] controller target id")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.__class__.__name__, 'NiTransformInterpolator', "Open sequence controlled_blocks[0] controller interpolator class")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.data.__class__.__name__, 'NiTransformData', "Open sequence controlled_blocks[0] controller interpolator data class")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.data.properties.xRotations.interpolation, NiKeyType.QUADRATIC_KEY, "Open sequence controlled_blocks[0] controller interpolator data xRotations interpolation")
    TT.assert_eq(len(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.data.xrotations), 2, "Open sequence controlled_blocks[0] controller interpolator data xRotations count")
    TT.assert_eq(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.data.xrotations[1].time, 0.5, "Open sequence controlled_blocks[0] controller interpolator data xRotations[1] time")
    TT.assert_equiv(nif.root.controller.sequences['Open'].controlled_blocks[0].interpolator.data.xrotations[1].value, -0.1222, "Open sequence controlled_blocks[0] controller interpolator data xRotations[1] value")


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


def Check_fo4MaleBody(nif:NifFile):

    # partitions property holds segment info for FO4 nifs. Body has 7 top-level segments
    TT.assert_eq(len(nif.shapes[0].partitions), 7, "number of partitions")
    
    # IDs assigned by nifly for reference
    TT.assert_seteq(set(x.name for x in nif.shapes[0].partitions), 
                    set(["FO4 Seg 000", "FO4 Seg 001", "FO4 Seg 002", "FO4 Seg 003", "FO4 Seg 004", "FO4 Seg 005", "FO4 Seg 006"]), 
                    "partitions")

    # Partition tri list gives the index of the associated partition for each tri in
    # the shape, so it's the same size as number of tris in shape
    TT.assert_eq(len(nif.shapes[0].partition_tris), 2698, "number of partition tris")

    # Shape has a segment file external to the nif
    TT.assert_eq(nif.shapes[0].segment_file, r"Meshes\Actors\Character\CharacterAssets\MaleBody.ssf", "segment file")

    # Subsegments hang off the segment/partition they are a part of.  They are given
    # names based on their "material" property.  That name includes the name of their
    # parent, so the parent figures out its own name from its subsegments.  This is
    # magic figured out by OS.
    TT.assert_eq(len(nif.shapes[0].partitions[0].subsegments), 0, "Segment 0 never has subsegments")
    TT.assert_eq(len(nif.shapes[0].partitions[1].subsegments), 0, "Body has no head subsegments")
    TT.assert_eq(len(nif.shapes[0].partitions[2].subsegments), 4, "number of subsegments in partition right arm")
    TT.assert_eq(nif.shapes[0].partitions[2].subsegments[0].name, "FO4 Seg 002 | 000 | Up Arm.R", "partition right arm subsegment name")
    TT.assert_contains("FO4 Seg 002 | 003 | Lo Arm.R", [s.name for s in nif.shapes[0].partitions[2].subsegments], "partition right arm subsegment name")

    # Segments and subsegments have IDs that run linearly increasing, in order. (This is a
    # bit of an accident, but the blender layer uses it.)
    allsegments = []
    allnames = []
    for p in nif.shapes[0].partitions:
        allsegments.append(p.id)
        allnames.append(p.name)
        for s in p.subsegments:
            allsegments.append(s.id)
            allnames.append(s.name)

    for i, n in enumerate(allsegments):
        assert i == n, f"Indicies are continuous"

    # Segments and subsegments are associated with triangles. There should be a
    # (sub)segment common to all verts of every triangle.
    assert len(nif.shapes[0].tris) == len(nif.shapes[0].partition_tris)
    t10 = nif.shapes[0].tris[0]
    s10 = nif.shapes[0].partition_tris[10]
    assert allnames[s10] == "FO4 Seg 002 | 000 | Up Arm.R", f"Have correct segment: {allnames[s10]}"


def Check_brickcolumn(nif:NifFile):
    # Check that we can read attributes from the materials file
    assert nif.shape_dict['DExBrickColumn01:0'].shader.materials is not None, "found material file"

    TT.assert_eq(nif.shape_dict['DExBrickColumn01:0'].shader.blockname, 'BSLightingShaderProperty', "shader class")
    # Check that the shader name path after 'data' is correct using pathlib
    shader_path = Path(nif.shape_dict['DExBrickColumn01:0'].shader.name)
    try:
        data_index = shader_path.parts.index('Data')
    except ValueError:
        data_index = shader_path.parts.index('data')
    after_data = Path(*shader_path.parts[data_index + 1:])
    TT.assert_eq(str(after_data), r"materials\Architecture\Buildings\BrickRed01.BGSM", "shader name")
    
    # Clamp mode is CLAMP in the nif but WRAP in the BGSM. Make sure we got the bgsm value.
    TT.assert_equiv(nif.shape_dict['DExBrickColumn01:0'].shader.properties.Env_Map_Scale, 0.5, "env mask scale")
    TT.assert_equiv(nif.shape_dict['DExBrickColumn01:0'].shader.properties.fresnelPower, 5.0, "fresnel power")
    TT.assert_eq(nif.shape_dict['DExBrickColumn01:0'].shader.flag_environment_mapping, True, "shader flag environment map")
    TT.assert_eq(nif.shape_dict['DExBrickColumn01:0'].shader.flag_greyscale_color, True, "shader flag greyscale to palette color")
    TT.assert_eq(nif.shape_dict['DExBrickColumn01:0'].shader.flag_zbuffer_write, True, "shader flag greyscale to palette color")
    TT.assert_eq(nif.shape_dict['DExBrickColumn01:0'].shader.texture_clamp_mode, 3, "texture clamp mode")


def Check_fo4Helmet(nif:NifFile):
    # partitions property holds segment info for FO4 nifs. Helmet has 2 top-level segments
    helm = nif.shape_dict['Helmet:0']
    TT.assert_eq(len(helm.partitions), 2, "helmet partitions")
    
    # IDs assigned by nifly for reference
    TT.assert_gt(helm.partitions[1].id, 0, "partition ID")
    TT.assert_eq(helm.partitions[1].name, "FO4 Seg 001", "partition name")

    # Partition tri list gives the index of the associated partition for each tri in
    # the shape, so it's the same size as number of tris in shape
    TT.assert_eq(len(helm.partition_tris), 2878, "Found expected tris")

    # Shape has a segment file external to the nif
    TT.assert_eq(helm.segment_file, r"Meshes\Armor\FlightHelmet\Helmet.ssf", "segment file")

    # Bodypart subsegments hang off the segment/partition they are a part of.  They are given
    # names based on their user_slot property.
    TT.assert_gt(len(helm.partitions[1].subsegments), 0, "Shapes have subsegments")
    TT.assert_eq(helm.partitions[1].subsegments[0].name, "FO4 Seg 001 | Hair Top | Head", "Subsegments have human-readable names")

    TT.assert_eq(helm.shader_block_name, "BSLightingShaderProperty", "shader")

    glass = nif.shape_dict['glass:0']
    TT.assert_eq(glass.partitions[1].subsegments[0].name, "FO4 Seg 001 | Hair Top", "glass has no bone ID")

    TT.assert_eq(glass.shader_block_name, "BSEffectShaderProperty", "effect shader")
    TT.assert_eq(glass.shader.name, r"Materials\Armor\FlightHelmet\glass.BGEM", "shader name")
    TT.assert_eq(glass.shader.flag_use_falloff, True, "use falloff")
    TT.assert_eq(glass.shader.flag_model_space_normals, False, "model space normals")
    TT.assert_eq(glass.shader.flag_environment_mapping, True, "environment mapping")
    TT.assert_eq(glass.shader.flag_effect_lighting, True, "effect lighting")

    TT.assert_eq(glass.shader.properties.textureClampMode, 3)
    TT.assert_eq(glass.shader.properties.falloffStartOpacity, 0.1)
    TT.assert_eq(glass.shader.properties.Emissive_Mult, 1.0)

    TT.assert_eq(glass.textures['Diffuse'], "Armor/FlightHelmet/Helmet_03_d.dds", "Diffuse")
    TT.assert_eq(glass.textures["Normal"], "Armor/FlightHelmet/Helmet_03_n.dds", "Normal")
    TT.assert_eq(glass.textures["EnvMapMask"], "Armor/FlightHelmet/Helmet_03_s.dds", "EnvMapMask")


test_files = {
    ("FO4", "VanillaMaleBody.nif"): Check_fo4MaleBody,
    ("FO4", "DExBrickColumn01.nif"): Check_brickcolumn,
    ("FO4", "Helmet.nif"): Check_fo4Helmet,
    ("SkyrimSE", "voidshade_1.nif"): CheckNif_voidshade,
    ("SkyrimSE","daedriccuirass_1.nif"): Check_daedriccuirass,
    ("Skyrim", "malehead.nif"): Check_malehead,
    ("Skyrim", "noblechest01.nif"): Check_noblechest01,
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