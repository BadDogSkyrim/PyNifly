"""Shaders, textures, colours and facegen tests. See tests/blender/__init__.py for how this package fits together."""

from .common import *
        

@TT.category('SKYRIMSE', 'SHADER')
def TEST_CHILDHEAD():
    """The child head has face tint but tangent space normals. Check it exports correctly."""

    testfile = TTB.test_file(r"tests\SkyrimSE\childhead.nif")
    outfile = TTB.test_file(r"tests/out/TEST_CHILDHEAD.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    head = bpy.context.object
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    nifout = pyn.NifFile(outfile)
    CHK.Check_childhead(nifout)


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_LE():
    """Shader attributes are read and turned into Blender shader nodes"""

    testfile = TTB.test_file(r"tests\Skyrim\meshes\actors\character\character assets\malehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_LE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)

    headobj = bpy.context.object
    TT.assert_contains('SkyrimShader:Face', headobj.active_material.node_tree.nodes, 
        f"Have face shader")
    bsdf = headobj.active_material.node_tree.nodes['SkyrimShader:Face']
    assert bsdf.inputs['Diffuse'].is_linked, f"Have a base color"
    diff_img = BD.find_node(bsdf.inputs['Diffuse'], "ShaderNodeTexImage")
    TT.assert_gt(len(diff_img), 0, f"Have diffuse texture image node")
    TT.assert_gt(len(diff_img[0].image.filepath), 0, f"Have diffuse texture filepath")
    assert bsdf.inputs['Normal'].is_linked, f"Have a normal map"
    assert bsdf.inputs['Diffuse'].is_linked, f"Have a base color"
    assert bsdf.inputs['Specular'].is_linked, f"Have specular"
    assert not bsdf.inputs['Specular Color'].is_linked, f"Specular color not linked"
    TT.assert_equiv(bsdf.inputs['Glossiness'].default_value, 33, f"Glossiness value")
    TT.assert_patheq(headobj.active_material['BSShaderTextureSet_SoftLighting'], 
                     r"textures\actors\character\male\MaleHead_sk.dds", 
                     f"stashed texture path")

    ### WRITE ###

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    ### CHECK ###

    nif = pyn.NifFile(testfile)
    head = nif.shapes[0]
    nifcheck = pyn.NifFile(outfile)
    headcheck = nifcheck.shapes[0]
    
    TT.assert_samemembers(headcheck.textures.keys(), head.textures.keys(), f"texture slots")
    for k in headcheck.textures:
        TT.assert_patheq(headcheck.textures[k], head.textures[k], f"{k} texture path")

    assert not headcheck.shader.properties.compare(head.shader.properties), \
        f"Shader properties correct: {headcheck.shader.properties.compare(head.shader.properties)}"


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_SE():
    """Shader attributes are read and turned into Blender shader nodes"""
    # Basic test of texture paths on shaders.

    fileSE = TTB.test_file(r"tests\SkyrimSE\meshes\armor\dwarven\dwarvenboots_envscale.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_SE.nif")
    
    bpy.ops.import_scene.pynifly(filepath=fileSE, blender_xf=True)
    nifSE = pyn.NifFile(fileSE)
    nifboots = nifSE.shapes[0]
    shaderAttrsSE = nifboots.shader.properties
    boots = bpy.context.object
    shadernodes = boots.active_material.node_tree.nodes
    TT.assert_gt(len(shadernodes), 4, "Number of shader nodes")
    TT.assert_eq(boots.active_material.pyn_shader.Env_Map_Scale, shaderAttrsSE.Env_Map_Scale, "environment map scale")
    TT.assert_eq(bpy.data.materials["Shoes.Mat"].node_tree.nodes["UV_Converter"].inputs[4].default_value, 1, "Wrap U")

    print("## Shader attributes are written on export")
    bpy.ops.object.select_all(action='DESELECT')
    boots.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = pyn.NifFile(outfile)
    CHK.Check_dwarvenboots(nifcheckSE)
    bootcheck = nifcheckSE.shapes[0]
    
    TT.assert_samemembers(bootcheck.textures.keys(), nifboots.textures.keys(), "Same textures")
    for k in bootcheck.textures:
        TT.assert_patheq(bootcheck.textures[k], nifboots.textures[k], f"{k} texture")

    diffs = bootcheck.shader.properties.compare(shaderAttrsSE)
    TT.assert_samemembers(diffs, [], f"difference in shader properties: {diffs}")
    TT.assert_eq(bootcheck.has_alpha_property, False, "has_alpha_property")


@TT.category('FO4', 'SHADER')
def TEST_SHADER_FO4():
    """Shader attributes are read and turned into Blender shader nodes"""
    fileFO4 = TTB.test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\basemalehead.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_FO4.nif")
    matin = TTB.test_file(r"tests\FO4\Materials\Actors\Character\BaseHumanMale\basehumanskinHead.bgsm")
    matout = TTB.test_file(r"tests\Out\Materials\Actors\Character\BaseHumanMale\basehumanskinHead.bgsm")

    bpy.ops.import_scene.pynifly(filepath=fileFO4, blender_xf=True)
    headFO4 = bpy.context.object

    # Blender evaluates a missing geometry attribute to ZERO, so an Attribute node naming one the
    # mesh doesn't have silently blackens whatever it feeds (how Starfield's naked_m imported
    # black). The FO4/Skyrim path names the actual color layer, so it can't dangle -- pinned here
    # because nothing else would notice if that changed.
    assert TT.is_eq(TTB.dangling_attribute_nodes(headFO4), [],
                    "no Attribute node names an attribute the mesh lacks")

    nifFO4 = pyn.NifFile(fileFO4)
    shapeorig = nifFO4.shapes[0]
    for t in ['Diffuse_Texture', 'Normal_Texture', 'Specular_Texture']:
        txt = headFO4.active_material.node_tree.nodes[t]
        assert txt and txt.image and txt.image.filepath, f"Imported texture {t}"

    # Shader attributes are written on export

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    # Put the materials file where the importer will find it.
    if not os.path.exists(matout):
        matdirout = os.path.split(matout)[0]
        shutil.os.makedirs(matdirout, exist_ok=True)
        shutil.copy(matin, matout)

    nifcheckFO4 = pyn.NifFile(outfile)
    
    shapecheck = nifcheckFO4.shapes[0]

    assert TT.is_samemembers(shapecheck.textures.keys(), 
        ('Wrinkles', 'RootMaterialPath', 'EnvMap', 'Specular', 'Normal', 'Diffuse',), 
        f"texture slots")
    assert TT.is_patheq(shapecheck.textures['Diffuse'], r"Actors\Character\BaseHumanMale\BaseMaleHead_d.dds", f"diffuse")
    assert TT.is_patheq(shapecheck.textures['Normal'], r"Actors\Character\BaseHumanMale\BaseMaleHead_n.dds", f"normal")
    assert TT.is_patheq(shapecheck.textures['Specular'], r"Actors\Character\BaseHumanMale\BaseMaleHead_s.dds", f"specular")

    assert not shapecheck.properties.compare(shapeorig.properties), \
        f"Shader attributes preserved: {shapecheck.properties.compare(shapeorig.properties)}"
    assert TT.is_eq(shapecheck.name, shapeorig.name, "shader name")

    # Environment Mapping flag on FO4 NIF causes CTDs — must never be set on export.
    assert not shapecheck.shader.properties.shaderflags1_test(pyn.ShaderFlags1.ENVIRONMENT_MAPPING), \
        "Environment Mapping flag must not be set on FO4 export"


@TT.category('FO4', 'SHADER')
def TEST_SHADER_GRAYSCALE_COLOR():
    """Test that grayscale color is handled directly"""
    testfile = TTB.test_file(r"tests\FO4\FemaleHair25.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_GRAYSCALE_COLOR.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    h = TTB.find_shape("FemaleHair25:0")
    m = h.active_material
    bsdf = m.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node

    # Greyscale palette correct
    vecnode = BD.find_node(bsdf.inputs['Diffuse'], 'ShaderNodeTexImage')[0]
    assert Path(vecnode.image.filepath).parts.index('haircolor_lgrad_d.dds') >= 0,  "Vector palette"
    difnode = BD.find_node(vecnode.inputs['Vector'], 'ShaderNodeTexImage')[0]
    assert Path(difnode.image.filepath).parts.index('haircurly_d.dds') >= 0,  "Diffuse texture"
    
    # UV scale correct
    uvnode = m.node_tree.nodes['UV_Converter']
    TT.assert_eq(uvnode.inputs['Scale U'].default_value, 
                 uvnode.inputs['Scale V'].default_value, 
                 1.0, 
                 "UV Scale")
    
    # Vertex alpha correct — FO4 always uses vertex alpha with vertex colors
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    vertalph = alpha.inputs['Vertex Alpha'].links[0].from_node
    TT.assert_eq(vertalph.attribute_type, 'GEOMETRY', "Geometry type")
    TT.assert_eq(vertalph.attribute_name, 'VERTEX_ALPHA', "Attribute name")

    # Specular texture connected
    specnode = BD.find_node(bsdf.inputs['Smooth Spec'], 'ShaderNodeTexImage')[0]
    assert Path(specnode.image.filepath).parts.index('haircurly_s.dds') >= 0, "specular"

    # Test export
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # Testing the attributes on the shader node, which is fine because they do get set.
    TTB.stage_materials_for(testfile, outfile)
    n1 = pyn.NifFile(testfile)
    n2 = pyn.NifFile(outfile)
    hair1 = n1.shapes[0]
    hair2 = n2.shapes[0]
    TT.assert_eq(hair2.shader.properties.UV_Scale_U, hair1.shader.properties.UV_Scale_U, "UV scale U")
    TT.assert_eq(hair2.properties.hasVertexColors, hair1.properties.hasVertexColors, "Vertex colors")


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_SCALE():
    """UV offset and scale are preserved."""
    testfile = TTB.test_file(r"tests\SkyrimSE\maleorchair27.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_SCALE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    n = pyn.NifFile(outfile)
    hair = n.shapes[0]
    assert hair.shader.properties.UV_Scale_U == 1.5, f"Have correct scale: {hair.shader.properties.UV_Scale_U}"


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_ALL():
    """Test that all texture slots are imported and exported correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\maleheadAllTextures.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_ALL.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    n = pyn.NifFile(outfile)
    head = n.shapes[0]
    TT.assert_eq_nocase(Path(head.shader.textures['Diffuse']).name, 'MaleHead.dds', 'diffuse texture')
    TT.assert_eq_nocase(Path(head.shader.textures['Normal']).name, 'MaleHead_msn.dds', 'MSN texture')
    TT.assert_eq_nocase(Path(head.shader.textures['SoftLighting']).name, 'MaleHead_sk.dds', 'Subsurface texture')
    TT.assert_eq_nocase(Path(head.shader.textures['HeightMap']).name, 'height.dds', 'Height map texture')
    TT.assert_eq_nocase(Path(head.shader.textures['EnvMap']).name, 'EnvMap.dds', 'Environment map texture')
    TT.assert_eq_nocase(Path(head.shader.textures['EnvMask']).name, 'EnvMask.dds', 'Environment mask texture')
    TT.assert_eq_nocase(Path(head.shader.textures['FacegenDetail']).name, 'Inner.dds', 'Facegen texture')
    TT.assert_eq_nocase(Path(head.shader.textures['Specular']).name, 'MaleHead_S.dds', 'Specular texture')
    TT.assert_eq(len(head.shader.textures), 8, "Head texture count")


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_EYE():
    """Test that all texture slots are imported and exported correctly."""
    testfile2 = TTB.test_file(r"tests\SkyrimSE\eyesmale.nif")
    outfile2 = TTB.test_file(r"tests/Out/TEST_SHADER_EYE.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile2)
    bpy.ops.export_scene.pynifly(filepath=outfile2)

    n = pyn.NifFile(outfile2)
    CHK.Check_eye(n)


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_ALPHA():
    """Shader attributes are read and turned into Blender shader nodes"""
    # Alpha property is translated into equivalent Blender nodes.
    #
    # Note this nif uses a MSN with a _n suffix. Import goes by the shader flag not the
    # suffix.

    fileAlph = TTB.test_file(r"tests\Skyrim\meshes\actors\character\Lykaios\Tails\maletaillykaios.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_ALPH.nif")

    bpy.ops.import_scene.pynifly(filepath=fileAlph)
    
    nifAlph = pyn.NifFile(fileAlph)
    furshape = nifAlph.shape_dict["tail_fur"]
    tail = bpy.data.objects["tail_fur"]
    TT.assert_contains('SkyrimShader:Default', tail.active_material.node_tree.nodes.keys(), "Shader")
    bsdf = tail.active_material.node_tree.nodes['SkyrimShader:Default']
    assert bsdf.inputs['Normal'].is_linked, f"Have normal map"
    TT.assert_contains('Diffuse_Texture', tail.active_material.node_tree.nodes.keys(), "Diffuse texture node")
    alpha = bsdf.inputs['Alpha Property'].links[0].from_node
    TT.assert_eq(alpha.inputs['Alpha Test'].default_value, True, "Alpha Test")
    TT.assert_eq(alpha.inputs['Alpha Blend'].default_value, False, "Alpha Blend")

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIM')

    nifCheck = pyn.NifFile(outfile)
    checkfurshape = nifCheck.shape_dict["tail_fur"]
    
    TT.assert_seteq(checkfurshape.shader.textures.keys(), furshape.shader.textures.keys(), "Textures")
    for k in checkfurshape.shader.textures:
        TT.assert_eq(checkfurshape.shader.textures[k], furshape.shader.textures[k], f"{k} texture")
    diffs = checkfurshape.shader.properties.compare(furshape.shader.properties)
    assert not diffs, f"No difference in properties: {diffs}"

    assert checkfurshape.has_alpha_property, f"Have alpha property"
    TT.assert_eq(checkfurshape.alpha_property.properties.flags, furshape.alpha_property.properties.flags, 
                 "Alpha flags")
    TT.assert_eq(checkfurshape.alpha_property.properties.threshold, furshape.alpha_property.properties.threshold, 
                 "Alpha threshold")


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_3_3():
    """Shader attributes are read and turned into Blender shader nodes"""
    # This older shader connects to the Principled BSDF "Subsurface" import port which
    # went away in V4.0, so it ain't never gonna work.
    if bpy.app.version[0] >= 4: return

    TTB.append_from_file("FootMale_Big", True, r"tests\SkyrimSE\feet.3.3.blend", 
                     r"\Object", "FootMale_Big")
    bpy.ops.object.select_all(action='DESELECT')
    obj = TTB.find_shape("FootMale_Big")

    print("## Shader attributes are written on export")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_3_3.nif")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheckSE = pyn.NifFile(outfile)
    
    shaderch = nifcheckSE.shapes[0].shader
    assert shaderch.textures['Diffuse'] == r"textures\actors\character\male\MaleBody_1.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Diffuse']}'"
    assert shaderch.textures['Normal'] == r"textures\actors\character\male\MaleBody_1_msn.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Normal']}'"
    assert shaderch.textures["SoftLighting"] == r"textures\actors\character\male\MaleBody_1_sk.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['SoftLighting']}'"
    assert shaderch.textures['Specular'] == r"textures\actors\character\male\MaleBody_1_S.dds", \
        f"Error: Texture paths not preserved: '{shaderch.textures['Specular']}'"


@TT.category('SKYRIM', 'SHADER')
def TEST_SHADER_EFFECT():
    """BSEffectShaderProperty attributes are read & written correctly."""
    testfile = TTB.test_file(r"tests\Skyrim\blackbriarchalet_test.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_SHADER_EFFECT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # nif = pyn.NifFile(testfile)
    nifcheck = pyn.NifFile(outfile)
    CHK.Check_blackbriarchalet(nifcheck)


@TT.category('SKYRIM', 'SHADER')
@TT.parameterize("txtdir", [r"tests\SkyrimSE", "xyzzy"])
def TEST_TEXTURE_PATHS(txtdir):
    """
    Texture paths are correctly resolved. Checks a texture file can be found using
    Blender's texture directory and when it can only be found relative to the nif.
    """
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\circletm1_test.nif")
    diffuse_file = TTB.test_file(r"tests\SkyrimSE\textures\test\circlet.dds")
    normal_file = TTB.test_file(r"tests\SkyrimSE\textures\test\circlet_n.dds")

    print(f"Testing with texture directory: {txtdir}")

    # Use temp_override to redirect the texture directory
    assert type(bpy.context) == bpy.types.Context, f"Context type is expected :{type(bpy.context)}"
    txtdir_in = bpy.context.preferences.filepaths.texture_directory
    if hasattr(bpy.context, 'temp_override'):
        # Blender 3.5
        with bpy.context.temp_override():
            bpy.context.preferences.filepaths.texture_directory = TTB.test_file(txtdir)
            bpy.ops.import_scene.pynifly(filepath=testfile)
    else:
            bpy.context.preferences.filepaths.texture_directory = TTB.test_file(txtdir)
            bpy.ops.import_scene.pynifly(filepath=testfile)
    
    # Should have found the texture files
    circlet = TTB.find_shape('M1:4')
    mat = circlet.active_material
    bsdf = mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
    diffuse = shader_io.get_image_filepath(bsdf.inputs['Diffuse'])
    assert TT.is_patheq(Path(diffuse), diffuse_file, f"diffuse texture path")
    norm = shader_io.get_image_filepath(bsdf.inputs['Normal'])
    assert TT.is_patheq(Path(norm), normal_file, "normal texture path")


@TT.category('SKYRIM', 'SHADER')
def TEST_CAVE_GREEN():
    """Cave nif can be exported correctly"""
    # Regression: Make sure the transparency is exported on this nif.
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\dungeons\caves\green\smallhall\caveghall1way01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_CAVE_GREEN.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    wall1 = bpy.data.objects["CaveGHall1Way01:2"]
    mat1 = wall1.active_material
    bsdf = mat1.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
    # mix1 = bsdf.inputs['Diffuse'].links[0].from_node
    # try:
    #     # Blender 3.5
    #     diff1 = mix1.inputs[6].links[0].from_node
    # except:
    #     # Blender 3.1
    #     diff1 = mix1.inputs['Color1'].links[0].from_node

    diff1 = BD.find_node(bsdf.inputs['Diffuse'], 'ShaderNodeTexImage')[0]
    assert diff1.image.filepath.lower()[0:-4].endswith("cavebasewall01"), \
        f"Have correct wall diffuse: {diff1.image.filepath}"
    
    assert bsdf.inputs['Vertex Color'].is_linked, "Vertex Color linked to node"
    n = BD.find_node(bsdf.inputs['Vertex Color'], 'ShaderNodeAttribute')[0]
    assert n.attribute_name == "VERTEX_COLOR", f"Using vertex colors"
    assert n.attribute_type == "GEOMETRY", f"Using vertex colors"

    roots = TTB.find_shape("L2_Roots:5")

    bpy.ops.object.select_all(action='DESELECT')
    roots.select_set(True)
    bpy.ops.object.duplicate()

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='SKYRIMSE')

    nifcheck = pyn.NifFile(outfile)
    rootscheck = nifcheck.shape_dict["L2_Roots:5"]
    assert rootscheck.has_alpha_property, f"Roots have alpha: {rootscheck.has_alpha_property}"
    assert rootscheck.shader.properties.shaderflags2_test(ShaderFlags2.VERTEX_COLORS), \
        f"Have vertex colors: {rootscheck.shader.properties.shaderflags2_test(ShaderFlags2.VERTEX_COLORS)}"


@TT.category('FO4', 'SHADER')
def TEST_BRICKWALL():
    """FO4 brick wall with greyscale, wild UV."""
    testfile = TTB.test_file(r"tests\FO4\Meshes\Architecture\DiamondCity\DExt\DExBrickColumn01.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile, create_bones=False, rename_bones=False)
    # This nif has clamped UVs in the nif, but the materials says they wrap. Make sure they wrap.
    TT.assert_eq(bpy.data.materials["DExBrickColumn01:0.Mat"].node_tree.nodes["UV_Converter"].inputs[4].default_value,
                    1, "UV S is clamped")
    assert bpy.data.materials["DExBrickColumn01:0.Mat"].node_tree.nodes["Fallout 4 MTS - Greyscale To Palette Vector"], "Have palette node"


@TT.category('FO4', 'SHADER')
def TEST_COLORS():
    """Can read & write vertex colors"""
    # Blender's vertex color layers are used to define vertex colors in the nif.
    outfile = TTB.test_file(r"tests/Out/TEST_COLORS_Plane.nif")
    TTB.export_from_blend(r"tests\FO4\VertexColors.blend", "Plane",
                      "FO4", outfile)

    nif3 = pyn.NifFile(outfile)
    assert len(nif3.shapes[0].colors) > 0, f"Expected color layers, have: {len(nif3.shapes[0].colors)}"
    cd = nif3.shapes[0].colors
    assert cd[0] == (0.0, 1.0, 0.0, 1.0), f"First vertex found: {cd[0]}"
    assert cd[1] == (1.0, 1.0, 0.0, 1.0), f"Second vertex found: {cd[1]}"
    assert cd[2] == (1.0, 0.0, 0.0, 1.0), f"Second vertex found: {cd[2]}"
    assert cd[3] == (0.0, 0.0, 1.0, 1.0), f"Second vertex found: {cd[3]}"


@TT.category('FO4', 'SHADER')
def TEST_COLORS2():
    """Can read & write vertex colors"""
    testfile = TTB.test_file(r"tests/FO4/HeadGear1.nif")
    testfileout = TTB.test_file(r"tests/Out/TEST_COLORS2.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert obj.data.attributes['VERTEX_COLOR'].domain == 'POINT', f"Have vertec colors in Blender"
    colordata = obj.data.attributes['VERTEX_COLOR'].data
    targetv = TTB.find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    assert colordata[targetv].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[targetv].color[:]}"
    # for lp in obj.data.loops:
    #     if lp.vertex_index == targetv:
    #         assert colordata[lp.index].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[lp.index].color[:]}"

    bpy.ops.export_scene.pynifly(filepath=testfileout, target_game="FO4")

    nif2 = pyn.NifFile(testfileout)
    assert nif2.shapes[0].colors[0] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not reread correctly: {nif2.shapes[0].colors[0]}"
    assert nif2.shapes[0].colors[561] == (0.0, 0.0, 0.0, 1.0), f"Color 561 not reread correctly: {nif2.shapes[0].colors[561]}"


@TT.category('FO4', 'SHADER')
def TEST_COLORS3():
    """Can read & write vertex colors & alpha"""
    testfile = TTB.test_file(r"tests\FO4\FemaleHair05_Hairline.nif")
    # testfile = TTB.test_file(r"tests\FO4\Meshes\Actors\Character\CharacterAssets\Hair\Male\Hair26_Hairline.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_COLORS3.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    nif = pyn.NifFile(testfile)
    c1229_nif = nif.shapes[0].colors[1229]
    blend_alphamap = bpy.context.object.data.attributes['VERTEX_ALPHA']
    c1229_blend = blend_alphamap.data[1229].color
    TT.assert_equiv(c1229_blend[0], c1229_nif[3], "Vertex alpha", e=1.0/255.0)

    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="FO4")

    nif2 = pyn.NifFile(outfile)
    colors = nif.shapes[0].colors
    colors2 = nif2.shapes[0].colors
    for i in range(0, len(colors)):
        TTB.test_floatarray(f"color {i}", colors[i], colors2[i], epsilon=(1.0/255.0))
        # assert colors[i] == colors2[i], f"Have correct colors, {colors[i]} == {colors2[i]}"


@TT.category('SKYRIMSE', 'SHADER')
def TEST_NEW_COLORS():
    """Can write vertex colors that were created in blender"""
    # Regression: There have been issues dealing with how Blender handles colors.
    outfile = TTB.test_file(r"tests/Out/TEST_NEW_COLORS.nif")

    TTB.export_from_blend(r"tests\SKYRIMSE\BirdHead.blend",
                      "HeadWhole",
                      "SKYRIMSE",
                      outfile)

    nif = pyn.NifFile(outfile)
    shape = nif.shapes[0]
    assert shape.colors, f"Have colors in shape {shape.name}"
    assert shape.colors[10] == (1.0, 1.0, 1.0, 1.0), f"Colors are as expected: {shape.colors[10]}"
    assert shape.shader.properties.shaderflags2_test(pyn.ShaderFlags2.VERTEX_COLORS), \
        f"ShaderFlags2 vertex colors set: {pyn.ShaderFlags2(shape.shader.Shader_Flags_2).fullname}"


@TT.category('SKYRIM', 'SHADER')
def TEST_COLOR_CUBES():
    """Can write vertex colors that were created in blender"""
    # Two shapes with the same name, both with vertex colors. Exporter should not get
    # confused.
    blendfile = TTB.test_file(r"tests\SKYRIM\ColorCubes.blend")
    outfile = TTB.test_file(r"tests/Out/TEST_COLOR_CUBES.nif")

    bpy.ops.wm.append(filepath=blendfile,
                        directory=blendfile + r"\Object",
                        filename="Cube")
    bpy.ops.wm.append(filepath=blendfile,
                        directory=blendfile + r"\Object",
                        filename="Cube.001")
    
    BD.ObjectSelect(bpy.context.scene.objects, active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

    nif = pyn.NifFile(outfile)

    # Find the cube at the origin
    bluegreen = next(s for s in nif.shapes if Vector(s.transform.translation) == Vector((0,0,0)))
    redgreen = next(s for s in nif.shapes if Vector(s.transform.translation) != Vector((0,0,0)))
    
    assert bluegreen.colors
    for c in bluegreen.colors:
        assert c == (0, 0, 1, 1) or c == (0, 1, 0, 1), f"Color is red or green: {c}"
    assert redgreen.colors
    for c in redgreen.colors:
        assert c == (1, 0, 0, 1) or c == (0, 1, 0, 1), f"Color is red or green: {c}"
        

@TT.expect_errors( ("Could not find materials file",))
@TT.category('FO4', 'SHADER')
def TEST_NOTEXTURES():
    """Can read a nif with no texture paths."""
    testfile = TTB.test_file(r"tests/FO4/HeadGear1 - NoTextures.nif")
    testfileout = TTB.test_file(r"tests/Out/TEST_NOTEXTURES.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    obj = bpy.context.object
    assert obj.data.attributes['VERTEX_COLOR'].domain == 'POINT', "Have vertex colors"
    colordata = obj.data.attributes['VERTEX_COLOR'].data
    targetv = TTB.find_vertex(obj.data, (1.62, 7.08, 0.37))
    assert colordata[0].color[:] == (1.0, 1.0, 1.0, 1.0), f"Color 0 not read correctly: {colordata[0].color[:]}"
    assert colordata[targetv].color[:] == (0.0, 0.0, 0.0, 1.0), f"Color for vert not read correctly: {colordata[targetv].color[:]}"


@TT.category('FO4', 'SHADER')
def TEST_VERTEX_COLOR_IO():
    """Vertex colors can be read and written"""
    # On heads, vertex alpha and diffuse alpha work together to determine the final
    # transparency the user sees. We set up Blender shader nodes to provide the same
    # effect.
    testfile = TTB.test_file(r"tests\FO4\FemaleEyesAO.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_COLOR_IO.nif", output=1)
    bpy.ops.import_scene.pynifly(filepath=testfile)

    eyes = TTB.find_shape("FemaleEyesAO:0")
    assert TT.is_contains('COLORS', eyes['pynVertexDesc'], "Eye vertex color flag")
    
    if bpy.app.version >= (3, 5, 0):
        # Color data handled differently in older versions
        colors = eyes.data.color_attributes.active_color.data
        max_r = max(c.color[0] for c in colors)
        min_r = min(c.color[0] for c in colors)
        assert max_r == 0, f"Have no white verts: {max_r}"
        assert min_r == 0, f"Have some black verts: {min_r}"

        # BSEffectShaderProperty is assumed to use the alpha channel if the shape has
        # transparency, whether or not ShaderFlagflag is set. Alpha is represented as ordinary
        # color on the VERTEX_ALPHA color attribute.
        colors = eyes.data.color_attributes['VERTEX_ALPHA'].data
        max_a = max(c.color[0] for c in colors)
        min_a = min(c.color[0] for c in colors)
        assert math.isclose(max_a, 1.0, abs_tol=0.001), f"Have some opaque verts: {max_a}"
        assert math.isclose(min_a, 0, abs_tol=0.001), f"Have some transparent verts: {min_a}"

    bpy.ops.object.select_all(action='DESELECT')
    eyes.select_set(True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game='FO4')

    assert os.path.exists(outfile), f"File created: {outfile}"

    TTB.stage_materials_for(outfile)
    nifcheck = pyn.NifFile(outfile)
    eyescheck = nifcheck.shapes[0]
    min_a = min(c[3] for c in eyescheck.colors)
    max_a = max(c[3] for c in eyescheck.colors)
    assert min_a == 0, f"Minimum alpha is 0: {min_a}"
    assert max_a == 1, f"Max alpha is 1: {max_a}"


@TT.category('SKYRIM', 'SHADER')
@TT.expect_errors( ("Some faces have been assigned to more than one partition",) )
def TEST_VERTEX_ALPHA_IO():
    """Import & export shape with vertex alpha values"""
    testfile = TTB.test_file(r"tests\SkyrimSE\meshes\actors\character\character assets\maleheadkhajiit.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_ALPHA_IO.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)

    head = bpy.context.object
    nodes = head.active_material.node_tree.nodes
    shader = nodes["SkyrimShader:Face"]
    assert shader, f"Found shader"
    diffuse = BD.find_node(shader.inputs["Diffuse"], "ShaderNodeTexImage")[0]
    TT.assert_eq(diffuse.bl_idname, "ShaderNodeTexImage", "diffuse shader node")
    TT.assert_eq_nocase(Path(diffuse.image.filepath).stem, 'KhajiitMaleHead', "diffuse file name")
    assert shader.inputs['Alpha Property'].is_linked, f"Have alpha map"

    bpy.ops.export_scene.pynifly(filepath=outfile)

    # nif = pyn.NifFile(testfile)
    # head1 = nif.shapes[0]
    nif2 = pyn.NifFile(outfile)
    CHK.Check_khajiithead(nif2)

    ## TODO: Ensure extra targets are correct
    ## TODO: Check the output nif visually. See that stage3 does the full fade out.    
    # # Not really sure what extra targets do, but make sure they're right
    # TT.assert_eq(len(nifout.root.controller.next_controller.extra_targets), 1, "extra targets count")


@TT.category('SKYRIM', 'SHADER')
def TEST_VERTEX_ALPHA():
    """Export shape with vertex alpha values"""
    outfile = TTB.test_file(r"tests/Out/TEST_VERTEX_ALPHA.nif")

    #---Create a shape
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.data.materials.append(bpy.data.materials.new("Material"))
    cube.active_material.use_nodes = True
    if bpy.app.version[0] >= 4:
        bpy.ops.geometry.color_attribute_add(
            name='COLOR', domain='POINT', data_type='FLOAT_COLOR', color=(1, 1, 1, 1))

        #store alpha 0.5
        bpy.ops.geometry.color_attribute_add(
            name=BD.ALPHA_MAP_NAME, domain='POINT', data_type='FLOAT_COLOR', color=(0.5, 0.5, 0.5, 1))

        #check that 0.5 is in fact stored as 188 after internal linear->sRGB conversion
        # for i, c in enumerate(bpy.context.object.data.vertex_colors[BD.ALPHA_MAP_NAME].data):
        #     assert math.floor(c.color[1] * 255) == 188, \
        #         f"Expected sRGB color {188.0 / 255.0}, found {i}: {c.color[:]}"

        #---Export it and check the NIF

        bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIM")

        nifcheck = pyn.NifFile(outfile)
        shapecheck = nifcheck.shapes[0]

        assert shapecheck.shader.properties.shaderflags1_test(pyn.ShaderFlags1.VERTEX_ALPHA), \
            f"Expected VERTEX_ALPHA set: {pyn.ShaderFlags1(shapecheck.shader.Shader_Flags_1).fullname}"

        #check that the NIF has alpha 0.5 (to byte precision only)
            # Works when alpha is read with alph.color
        assert math.isclose(shapecheck.colors[0][3], 0.5, abs_tol=(1.0 / 255.0)), \
            f"Expected alpha 0.5, found {shapecheck.colors[0][3]}"

        for c in shapecheck.colors:
            assert c[0] == 1.0 and c[1] == 1.0 and c[2] == 1.0, \
                f"Expected all white verts in nif, found {c}"

        #---Import it back

        bpy.ops.import_scene.pynifly(filepath=outfile)
        objcheck = bpy.context.object
        try:
            alphamap = objcheck.data.attributes[BD.ALPHA_MAP_NAME]
        except:
            alphamap = objcheck.data.vertex_colors[BD.ALPHA_MAP_NAME]
        assert alphamap.name == BD.ALPHA_MAP_NAME, f"Expected alpha map"

        #check that imported color is still 188
        for i, c in enumerate(alphamap.data):
            TT.assert_equiv(c.color[1], 0.5, "alpha value")

        for i, c in enumerate(objcheck.data.attributes['VERTEX_COLOR'].data):
            TT.assert_equiv(c.color, (1.0, 1.0, 1.0, 1.0), "color value")


@TT.category('FO4', 'LOD', 'SHADER')
def TEST_TRASH_EDGE():
    """FO4 LOD edge cases and vertex alpha without VERTEX_ALPHA shader flag."""
    # TrashEdge01.nif exercises two FO4 issues:
    #   1. LOD distribution with empty buckets:
    #      - L1_TrashEdge01:0  has lodSize 0 / 93  / 0   (everything in LOD1)
    #      - L2_TrashDecal01:1 has lodSize 0 / 0   / 300 (everything in LOD2)
    #   2. L1_TrashEdge01:0 has per-vertex alpha (some verts a=0, some a=1)
    #      but the BSLightingShaderProperty does NOT set the VERTEX_ALPHA flag.
    #      In FO4 the SLSF1_VERTEX_ALPHA flag is vestigial — the vertex stream
    #      carries alpha whenever the vertex format includes colors, and the
    #      BGSM decides whether it's blended at runtime. The importer must
    #      still round-trip that alpha data faithfully.
    testfile = TTB.test_file(r"tests\FO4\meshes\TrashEdge01.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_TRASH_EDGE.nif", output=True)

    # ------- Capture expected values from source --------
    nif_in = pyn.NifFile(testfile)
    src_edge = nif_in.shape_dict['L1_TrashEdge01:0']
    src_decal = nif_in.shape_dict['L2_TrashDecal01:1']

    assert TT.is_eq(src_edge.properties.lodSize0, 0,  "Source edge LOD0")
    assert TT.is_eq(src_edge.properties.lodSize1, 93, "Source edge LOD1")
    assert TT.is_eq(src_edge.properties.lodSize2, 0,  "Source edge LOD2")
    assert TT.is_eq(src_decal.properties.lodSize0, 0,   "Source decal LOD0")
    assert TT.is_eq(src_decal.properties.lodSize1, 0,   "Source decal LOD1")
    assert TT.is_eq(src_decal.properties.lodSize2, 300, "Source decal LOD2")

    # Edge has per-vertex colors with meaningful alpha (shader flags don't
    # matter in FO4; we check the vertex stream directly).
    assert TT.is_gt(len(src_edge.colors), 0, "Source edge has vertex colors")
    src_edge_alphas = [c[3] for c in src_edge.colors]
    assert TT.is_eq(min(src_edge_alphas), 0.0, "Source edge has alpha=0 verts")
    assert TT.is_eq(max(src_edge_alphas), 1.0, "Source edge has alpha=1 verts")

    # ------- Import --------
    bpy.ops.import_scene.pynifly(filepath=testfile, create_collection=True)

    edge = next(o for o in bpy.data.objects
                if o.type == 'MESH' and o.name.startswith('L1_TrashEdge01'))
    decal = next(o for o in bpy.data.objects
                 if o.type == 'MESH' and o.name.startswith('L2_TrashDecal01'))

    # LOD modifiers should exist on both shapes
    assert edge.modifiers.get("LOD") is not None,  "Edge has LOD mask modifier"
    assert decal.modifiers.get("LOD") is not None, "Decal has LOD mask modifier"

    # All three LOD groups should always be created, even when buckets are empty.
    edge_lod_groups = [g.name for g in edge.vertex_groups if g.name in BD.LOD_GROUP_NAMES]
    assert TT.is_eq(sorted(edge_lod_groups), ["LOD0", "LOD1", "LOD2"],
                    "Edge has all 3 LOD vertex groups")
    decal_lod_groups = [g.name for g in decal.vertex_groups if g.name in BD.LOD_GROUP_NAMES]
    assert TT.is_eq(sorted(decal_lod_groups), ["LOD0", "LOD1", "LOD2"],
                    "Decal has all 3 LOD vertex groups")

    # Edge cumulative membership: LOD0 empty, LOD1 = LOD2 = all 94 verts.
    def vg_vert_count(obj, name):
        gi = obj.vertex_groups[name].index
        return sum(1 for v in obj.data.vertices if any(g.group == gi for g in v.groups))
    assert TT.is_eq(vg_vert_count(edge, "LOD0"), 0, "Edge LOD0 empty")
    assert TT.is_eq(vg_vert_count(edge, "LOD1"), len(edge.data.vertices), "Edge LOD1 = all verts")
    assert TT.is_eq(vg_vert_count(edge, "LOD2"), len(edge.data.vertices), "Edge LOD2 = all verts")

    # Decal cumulative membership: LOD0 = LOD1 = empty, LOD2 = all verts.
    assert TT.is_eq(vg_vert_count(decal, "LOD0"), 0, "Decal LOD0 empty")
    assert TT.is_eq(vg_vert_count(decal, "LOD1"), 0, "Decal LOD1 empty")
    assert TT.is_eq(vg_vert_count(decal, "LOD2"), len(decal.data.vertices), "Decal LOD2 = all verts")

    # Diffuse texture should be loaded on the edge material. The importer
    # creates a 'Diffuse_Texture' ShaderNodeTexImage and sets its image.
    assert edge.active_material is not None, "Edge has a material"
    diff_node = edge.active_material.node_tree.nodes.get('Diffuse_Texture')
    assert diff_node is not None, "Edge has Diffuse_Texture node"
    assert diff_node.image is not None, "Edge diffuse texture image is loaded"
    assert TT.is_gt(len(diff_node.image.filepath), 0, "Edge diffuse texture filepath set")
    assert TT.is_gt(len(diff_node.image.pixels), 0, "Edge diffuse image has pixel data")

    # The source nif has no NiAlphaProperty block on the edge shape, but its
    # BGSM has alphatest set, so the importer must synthesize an Alpha
    # Property shader node from the BGSM. (We confirmed source has no block.)
    assert not src_edge.has_alpha_property, "Source edge has no NiAlphaProperty block"
    edge_mat = edge.active_material
    assert edge_mat is not None, "Edge has a material"
    assert 'Alpha Property' in (n.label for n in edge_mat.node_tree.nodes) \
        or any('Alpha Property' in n.name for n in edge_mat.node_tree.nodes), \
        "Edge material has an Alpha Property shader node"

    # Vertex alpha layer must be created on the edge even though the
    # VERTEX_ALPHA shader flag is not set, because the alpha data is real.
    assert BD.ALPHA_MAP_NAME in edge.data.color_attributes, \
        "Edge has VERTEX_ALPHA color attribute despite shader flag not being set"
    alphmap = edge.data.color_attributes[BD.ALPHA_MAP_NAME]
    a_vals = [alphmap.data[i].color[0] for i in range(len(alphmap.data))]
    assert TT.is_eq(min(a_vals), 0.0, "Imported edge alpha minimum is 0")
    assert TT.is_eq(max(a_vals), 1.0, "Imported edge alpha maximum is 1")

    # ------- Export --------
    BD.ObjectSelect([edge, decal,
                     next(o for o in bpy.data.objects if 'pynRoot' in o)],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    # ------- Check --------
    nif_out = pyn.NifFile(outfile)
    out_edge = nif_out.shape_dict['L1_TrashEdge01:0']
    out_decal = nif_out.shape_dict['L2_TrashDecal01:1']

    # LOD sizes round-trip
    assert TT.is_eq(out_edge.properties.lodSize0, 0,  "Edge LOD0 round-trips")
    assert TT.is_eq(out_edge.properties.lodSize1, 93, "Edge LOD1 round-trips")
    assert TT.is_eq(out_edge.properties.lodSize2, 0,  "Edge LOD2 round-trips")
    assert TT.is_eq(out_decal.properties.lodSize0, 0,   "Decal LOD0 round-trips")
    assert TT.is_eq(out_decal.properties.lodSize1, 0,   "Decal LOD1 round-trips")
    assert TT.is_eq(out_decal.properties.lodSize2, 300, "Decal LOD2 round-trips")

    # Vertex alpha round-trips on the edge: still has both 0 and 1 alphas.
    assert TT.is_gt(len(out_edge.colors), 0, "Edge still has vertex colors")
    out_alphas = [c[3] for c in out_edge.colors]
    assert TT.is_eq(min(out_alphas), 0.0, "Edge alpha=0 verts round-trip")
    assert TT.is_eq(max(out_alphas), 1.0, "Edge alpha=1 verts round-trip")

    # The exporter must NOT add a NiAlphaProperty block to the edge shape:
    # the source nif had none and the alpha info lives in the BGSM, not the
    # nif. Adding a block would change the file's structure on round-trip.
    assert not out_edge.has_alpha_property, \
        "Exported edge must not have a NiAlphaProperty block"


@TT.category('FO4', 'SHADER')
@TT.expect_errors(("Could not find materials file",))
def TEST_NORM():
    """Normals are read correctly"""
    testfile = TTB.test_file(r"tests/FO4/Meshes/CheetahMaleHead.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    head = TTB.find_shape("CheetahMaleHead")

    if hasattr(head.data, "calc_normals_split"):
        head.data.calc_normals_split()

    # Lower left neck seam has correct split normal
    targetvert = head.data.vertices[3071]
    TT.assert_equiv(targetvert.co, [-4.8594, 2.3613, -10.5468], "vertex position", e=0.01)
    if bpy.app.version < (4, 4, 0):
        # Later versions of blender seem to always return the custom normal
        TT.assert_equiv(targetvert.normal, [-0.4079, 0.4657, 0.7854], "vertex normal", e=0.01)

    targetloops = [lp for lp in head.data.loops if lp.vertex_index == 3071]
    TT.assert_equiv(targetloops[0].normal, [-0.207843, 0.435294, 0.874510], "loop normal", e=0.01)


@TT.category('FO4', 'SHADER')
def TEST_SPLIT_NORMALS():
    """Mesh with wonky normals exports correctly"""
    # Custom split normals change the direction light bounces off an object. They may be
    # set to eliminate seams between parts of a mesh, or between two meshes.

    testfile = TTB.test_file(r"tests/Out/TEST_SPLIT_NORMALS.nif")

    obj = TTB.append_from_file("MHelmetLight:0", 
                              False, 
                              r"tests\FO4\WonkyNormals.blend", 
                              r"\Object", 
                              "MHelmetLight:0")
    assert obj.name == "MHelmetLight:0", "Got the right object"

    bpy.ops.export_scene.pynifly(filepath=testfile, target_game="FO4")

    nif2 = pyn.NifFile(testfile)
    shape2 = nif2.shapes[0]

    TTB.test_floatarray("Normal 44", shape2.normals[44], [0, 0, 1], epsilon=0.1)
    TTB.test_floatarray("Vert 12 location", shape2.verts[12], [6.82, 0.58, 9.05], epsilon=0.01)
    TTB.test_floatarray("Vert 5 location", shape2.verts[5], [0.13, 9.24, 8.91], epsilon=0.01)
    TTB.test_floatarray("Vert 33 location", shape2.verts[33], [-3.21, -1.75, 12.94], epsilon=0.01)

    # Original has a tri <12, 13, 14>. Find it in the original and then in the exported object

    found = -1
    target = set([12, 13, 14])
    for p in obj.data.polygons:
        ps = set([obj.data.loops[lp].vertex_index for lp in p.loop_indices])
        if ps == target:
            print(f"Found triangle in source mesh at {p.index}")
            found = p.index
            break
    assert found >= 0, "Triangle not in source mesh"

    found = -1
    for i, t in enumerate(shape2.tris):
        if set(t) == target:
            print(f"Found triangle in target mesh at {i}")
            found = i
            break
    assert found >= 0, "Triangle not in output mesh"


@TT.category('SKYRIM', 'SHADER', 'SHAPEKEYS')
def TEST_ROGUE02():
    """Shape keys export normals correctly"""
    # Shape keys and custom normals interfere with each other. If a shape key warps the
    # mesh, what direction should a custom normal face after the warp? We just preserve
    # the direction and leave it to the user to separate out the shape key if they don't
    # like the result.
    testfile = TTB.test_file(r"tests/Out/TEST_ROGUE02.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_ROGUE02_warp.nif")

    TTB.export_from_blend(r"tests\Skyrim\ROGUE02-normals.blend",
                         "Plane", "SKYRIM", testfile, "_warp")

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    assert len(shape2.verts) == 25, f"Export shouldn't create extra vertices, found {len(shape2.verts)}"
    v = [round(x, 1) for x in shape2.verts[18]]
    assert v == [0.0, 0.0, 0.2], f"Vertex found at incorrect position: {v}"
    n = [round(x, 1) for x in shape2.normals[8]]
    assert n == [0, 1, 0], f"Normal should point along y axis, instead: {n}"


@TT.category('FO4', 'SHADER')
def TEST_NORMAL_SEAM():
    """Normals on a split seam are seamless"""
    testfile = TTB.test_file(r"tests/Out/TEST_NORMAL_SEAM.nif")
    outfile = TTB.test_file(r"tests/Out/TEST_NORMAL_SEAM_Dog.nif")

    TTB.export_from_blend(r"tests\FO4\TestKnitCap.blend", "MLongshoremansCap:0",
                      "FO4", testfile)

    nif2 = pyn.NifFile(outfile)
    shape2 = nif2.shapes[0]
    target_vert = [i for i, v in enumerate(shape2.verts) if NT.VNearEqual(v, (0.00037, 7.9961, 9.34375))]

    assert len(target_vert) == 2, f"Expect vert to have been split: {target_vert}"
    assert NT.VNearEqual(shape2.normals[target_vert[0]], shape2.normals[target_vert[1]]), f"Normals should be equal: {shape2.normals[target_vert[0]]} != {shape2.normals[target_vert[1]]}" 


@TT.category('SKYRIM', 'SHADER')
def TEST_IMP_NORMALS():
    """Can import normals from nif shape"""

    testfile = TTB.test_file(r"tests/Skyrim/cube.nif")
    bpy.ops.import_scene.pynifly(filepath=testfile)

    # all loop custom normals point off at diagonals
    obj = bpy.context.object
    try:
        obj.data.calc_normals_split()
    except:
        pass
    for l in obj.data.loops:
        for i in [0, 1, 2]:
            assert round(abs(l.normal[i]), 3) == 0.577, f"Expected diagonal normal, got loop {l.index}/{i} = {l.normal[i]}"


@TT.category('SKYRIM', 'SHADER')
def TEST_UV_SPLIT():
    """Can split UVs properly"""
    filepath = TTB.test_file("tests/Out/TEST_UV_SPLIT.nif")

    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.export_scene.pynifly(filepath=filepath, target_game="SKYRIM")
    
    nif_in = pyn.NifFile(filepath)
    obj = nif_in.shapes[0]
    assert TT.is_gt(len(obj.verts), 8, "Verts were split from UV seams")
    assert TT.is_eq(len(obj.uvs), len(obj.verts), "Same number of UV points as verts")
    # Find a pair of split verts: same position, different UVs
    found_split = False
    for i in range(len(obj.verts)):
        for j in range(i+1, len(obj.verts)):
            if NT.VNearEqual(obj.verts[i], obj.verts[j]) and not NT.VNearEqual(obj.uvs[i], obj.uvs[j]):
                found_split = True
                break
        if found_split:
            break
    assert TT.is_eq(found_split, True, "Found split verts at same location with different UVs")


@TT.category('SKYRIM', 'SHADER')
def TEST_TEXTURE_CLAMP():
    """Make sure we don't lose texture clamp mode."""
    testfile = TTB.test_file(r"tests\SkyrimSE\evergreen.nif")
    outfile = TTB.test_file(r"tests\out\TEST_TEXTURE_CLAMP.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile, blender_xf=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile)
    TT.assert_eq(nifin.shapes[0].shader.properties.textureClampMode,
            nifout.shapes[0].shader.properties.textureClampMode, \
            "clamp mode")


@TT.category('FO4', 'SHADER')
@TT.expect_errors(('Could not load diffuse texture',
                   'Could not load normal texture',
                   'Could not find texture',
                   'Could not find materials file',))
def TEST_MISSING_MAT():
    """We import and export properly even when files are missing."""
    testfile = TTB.test_file(r"tests\FO4\malehandsalt.nif")
    outfile = TTB.test_file(r"tests\out\TEST_MISSING_MAT.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)
    hands = bpy.context.object
    mat = hands.active_material
    assert mat['BSLSP_Shader_Name'] == r"Materials\foo\basehumanmaleskinhands.bgsm", \
        f"Have correct materials: {mat['BS_Shader_Block_Name']}"
    # assert 'SKIN_TINT' in mat.pyn_shader.Shader_Flags_1, f"Have correct flags: {mat.pyn_shader.Shader_Flags_1}"
    assert mat.pyn_shader.Shader_Type == 'Skin_Tint', f"Have correct shader type: {mat.pyn_shader.Shader_Type}"
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifin = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile)
    assert (nifin.shapes[0].shader.properties.textureClampMode 
            == nifout.shapes[0].shader.properties.textureClampMode), \
        f"Preserved texture clamp mode: {nifout.shapes[0].shader.textureClampMode}"


@TT.category('FO4', 'SHADER')
def TEST_SCAFFOLD_FRAME():
    """We truncate long filepaths to relative paths."""
    testfile = TTB.test_file(r"tests\FO4\ScaffFrame1x2Str01.nif")
    outfile = TTB.test_file(r"tests\out\TEST_SCAFFOLD_FRAME.nif")

    bpy.ops.import_scene.pynifly(filepath=testfile)

    # Materiai nodes reasonably clustered
    obj = bpy.context.object
    mat = obj.active_material
    node_bounds = (min((n.location.x for n in mat.node_tree.nodes)),
                   max((n.location.x for n in mat.node_tree.nodes)),
                   min((n.location.y for n in mat.node_tree.nodes)),
                   max((n.location.y for n in mat.node_tree.nodes)),)
    TT.assert_lt(node_bounds[1] - node_bounds[0], 2000, "Material node X bounds")
    TT.assert_lt(node_bounds[3] - node_bounds[2], 2000, "Material node Y bounds")

    # Material path read correctly
    TT.assert_pathendswith(
        mat['BSLSP_Shader_Name'], 
        r"materials\Architecture\Quarry\QryCatwalksBluePaint.BGSM", 
        "material path")
    
    # Image nodes exist
    TT.assert_samemembers(
        [Path(NT.truncate_filename(n.image.filepath, 'textures')) 
            for n in obj.active_material.node_tree.nodes if n.type == 'TEX_IMAGE'],
        [Path('architecture/quarry/qrycatwalksbluepaint_d.dds'), 
            Path('architecture/quarry/qrycatwalksbluepaint_n.dds'), 
            Path('architecture/quarry/qrycatwalksbluepaint_s.dds')],
        "Image texture nodes")

    bpy.ops.export_scene.pynifly(filepath=outfile)

    TTB.stage_materials_for(testfile, outfile)
    nifin = pyn.NifFile(testfile)
    nifout = pyn.NifFile(outfile)
    assert (nifin.shapes[0].shader.properties.textureClampMode
            == nifout.shapes[0].shader.properties.textureClampMode), \
        f"Preserved texture clamp mode: {nifout.shapes[0].shader.textureClampMode}"


@TT.category('FO4', 'SHADER')
@TT.expect_errors(("Could not find materials file",))
def TEST_MISSING_FILES():
    """Write a good nif even if texture and materials files are missing."""
    blendfile = TTB.test_file(r"tests\FO4\Gloves.blend")
    outfile = TTB.test_file(r"tests\out\TEST_MISSING_FILES.nif")

    # Can't load the test blend file in 3.x
    if bpy.app.version[0] <= 3: return

    # append all objects starting with 'house'
    with bpy.data.libraries.load(blendfile) as (data_from, data_to):
        data_to.objects = [obj for obj in data_from.objects]

    # link them to scene
    scene = bpy.context.scene
    for obj in data_to.objects:
        if obj is not None:
            scene.collection.objects.link(obj)

    hands = next(obj for obj in bpy.context.scene.objects if obj.name.startswith('BaseMaleHands'))
    hands.active_material['BS_Shader_Block_Name'] = "BSLightingShaderProperty"
    hands.active_material['Shader_Type'] = "Skin_Tint"
    hands.active_material['BSShaderTextureSet_Diffuse'] = "actors/character/basehumanmale/basemalehands_d.dds"
    BD.ObjectSelect([obj for obj in bpy.context.scene.objects if 'pynRoot' in obj],
                    active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile)

    nifout = pyn.NifFile(outfile)
    handsout = nifout.shape_dict['BaseMaleHands3rd_fitted:0']
    assert handsout.shader.name == r"Materials\actors\Character\BaseHumanMale\basehumanmaleskinhands.bgsm", \
        f"Have correct shader name: {handsout.shader.name}"
    # NOT WORKING: We should be able to set the shader type this way but in fact it's 
    # not working all the way down to the nifly level. Not sure why.
    # assert handsout.shader.properties.Shader_Type == BSLSPShaderType.Skin_Tint, \
    #     f"Have correct shader: {handsout.shader.properties.Shader_Type}"
    assert r"textures\actors\character\basehumanmale\basemalehands_d.dds" == handsout.textures['Diffuse'], \
        f"Have diffuse in texture list: {handsout.textures}"
    # assert body.properties.broadPhaseType == BroadPhaseType.ENTITY, "Have correct broad phase type"
    # assert body.properties.collisionResponse2 == hkResponseType.SIMPLE_CONTACT, "Have correct CollisionResponse2"
    # assert body.properties.processContactCallbackDelay == 65535, "Have correct processContactCallbackDelay"
    # assert body.properties.rollingFrictionMult == 0, "Have correct rollingFrictionMult"
    # assert body.properties.motionSystem == hkMotionType.SPHERE_STABILIZED, "Have correct motionSystem"
    # assert body.properties.solverDeactivation == hkSolverDeactivation.LOW, "Have correct solverDeactivation"
    # assert body.properties.qualityType == hkQualityType.MOVING, "Have correct qualityType"


@TT.category('FO4', 'FACEGEN')
def TEST_FACEGEN():
    # FO4 facegen files are wonky. They have bones in the right positions, but without the
    # proper rotations. Fixing the rotations in the nif file shows the mesh undistorted.
    # So we need to figure out how to do the equivalent on import. Probably we should also
    # have an explicit "facgen" flag so the importer doesn't have to guess.
    """
    FO4 facegen import works--imported head is not distorted.
    """
    testfile = TTB.test_file(r"tests\FO4\Meshes\facegen.nif")

    # Can't import pose locations for facegen files. This is testing that it works
    # correctly anyway.
    bpy.ops.import_scene.pynifly(filepath=testfile, 
                                 create_bones=False,
                                 import_pose=True)
    head = [obj for obj in bpy.context.selected_objects if obj.name.startswith('FFODeerMaleHead')][0]
    eyes = [obj for obj in bpy.context.selected_objects if obj.name.startswith('FFOUngulateMaleEyes')][0]

    # Head in world coordinates should be taller than wide.
    diag = TTB.get_obj_bbox(head, worldspace=True);
    assert diag[1].x-diag[0].x < diag[1].z-diag[0].z, f"Head is taller than wide: {diag[1]-diag[0]}"
    exmin = min((eyes.matrix_world @ v.co).x for v in eyes.data.vertices)
    exmax = max((eyes.matrix_world @ v.co).x for v in eyes.data.vertices)
    assert BD.NearEqual(exmin, -4.7, epsilon=0.1), f"Eye min X correct: {exmin}"
    assert BD.NearEqual(exmax, 4.7, epsilon=0.1), f"Eye max X correct: {exmax}"


@TT.category('SKYRIMSE', 'FACEGEN')
@TT.expect_errors(('Some faces have been assigned to more than one partition',))
def TEST_FACEGEN_SE():
    """Skyrim SE facegen file round-trips correctly."""
    testfile = TTB.test_file(r"tests\SkyrimSE\facegen.nif")
    outfile = TTB.test_file(r"tests/out/TEST_FACEGEN_SE.nif")

    nifin = pyn.NifFile(testfile)
    in_shape_names = [s.name for s in nifin.shapes]
    head_in_verts = len(nifin.shape_dict['YASLykaiosMaleHead'].verts)

    # Import into its own collection.
    bpy.ops.import_scene.pynifly(filepath=testfile,
                                 create_bones=False,
                                 import_pose=True,
                                 create_collection=True)

    meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    head = [obj for obj in meshes if obj.name.startswith('YASLykaiosMaleHead')][0]

    # All head parts should occupy roughly the same volume, positioned like a head.
    bboxes = {}
    for obj in meshes:
        bboxes[obj.name] = TTB.get_obj_bbox(obj, worldspace=True)

    head_bb = bboxes[head.name]
    head_height = head_bb[1].z - head_bb[0].z
    head_width = head_bb[1].x - head_bb[0].x

    # Head should be taller than wide and reasonably sized (not collapsed or giant).
    assert TT.is_gt(head_height, head_width, "Head taller than wide")
    assert TT.is_gt(head_height, 10, "Head has reasonable height")
    assert TT.is_lt(head_height, 40, "Head not oversized")

    # All parts should overlap the head bounding box -- none should be wildly misplaced.
    for name, bb in bboxes.items():
        assert TT.is_lt(bb[0].z, head_bb[1].z,
                         f"{name} overlaps head Z range")
        assert TT.is_gt(bb[1].z, head_bb[0].z,
                         f"{name} overlaps head Z range")

    # Export all facegen shapes.
    BD.ObjectSelect(meshes, active=True)
    bpy.ops.export_scene.pynifly(filepath=outfile, target_game="SKYRIMSE")

    # Verify round-trip
    nifout = pyn.NifFile(outfile)
    out_shape_names = [s.name for s in nifout.shapes]
    assert TT.is_eq(sorted(out_shape_names), sorted(in_shape_names),
                     "All shapes exported")
    assert TT.is_eq(len(nifout.shape_dict['YASLykaiosMaleHead'].verts),
                     head_in_verts, "Head vert count preserved")

    # Deselect everything so the reimport doesn't merge as a shape key.
    bpy.ops.object.select_all(action='DESELECT')

    # Re-import the exported file into a separate collection for easy inspection.
    bpy.ops.import_scene.pynifly(filepath=outfile,
                                 create_bones=False,
                                 import_pose=True,
                                 create_collection=True)
    re_head = [obj for obj in bpy.context.selected_objects
               if obj.name.startswith('YASLykaiosMaleHead')][0]
    re_bb = TTB.get_obj_bbox(re_head, worldspace=True)
    assert TT.is_equiv(re_bb[1].z - re_bb[0].z, head_height,
                        "Re-imported head height matches",
                        e=0.1)
