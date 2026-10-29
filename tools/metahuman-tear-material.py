"""Native deferred-decal wet film: no painted white streak or face texture edit."""
import unreal

def make_tear_material():
    path='/Game/Audition/Tears/M_TearFilm'
    mat=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_TearFilm','/Game/Audition/Tears',unreal.Material,unreal.MaterialFactoryNew())
    lib=unreal.MaterialEditingLibrary
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('material_domain',unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
    uv=lib.create_material_expression(mat,unreal.MaterialExpressionTextureCoordinate,-700,0)
    clock=lib.create_material_expression(mat,unreal.MaterialExpressionTime,-700,100)
    wet=lib.create_material_expression(mat,unreal.MaterialExpressionScalarParameter,-700,200)
    wet.set_editor_property('parameter_name','Wetness');wet.set_editor_property('default_value',.9)
    phase=lib.create_material_expression(mat,unreal.MaterialExpressionScalarParameter,-700,300)
    phase.set_editor_property('parameter_name','Phase');phase.set_editor_property('default_value',0.)
    effect=lib.create_material_expression(mat,unreal.MaterialExpressionCustom,-400,0)
    effect.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    inputs=[]
    for name in ['UV','Clock','Wetness','Phase']:
        value=unreal.CustomInput();value.set_editor_property('input_name',name);inputs.append(value)
    effect.set_editor_property('inputs',inputs)
    effect.set_editor_property('code','''
// Unreal decal UVs are local Z,Y. Remap to horizontal and downward.
float2 p=float2(UV.y,1-UV.x);
float v=p.y;
float center=.5 + .055*sin(v*7.0+Phase);
float width=lerp(.028,.016,v);
float dx=p.x-center;
float edge=1-smoothstep(width*.55,width,abs(dx));
float ends=smoothstep(.015,.055,v)*(1-smoothstep(.87,.98,v));
float dropY=frac(Clock*.17+Phase);
float dropX=.5+.055*sin(dropY*7+Phase);
float2 d=(p-float2(dropX,dropY))/float2(.046,.035);
float drop=(1-smoothstep(.4,1,length(d)))*smoothstep(.04,.1,dropY)*(1-smoothstep(.85,.97,dropY));
float film=edge*ends;
float mask=max(film*.76,drop*.95)*saturate(Wetness);
float3 n=normalize(float3(-.015*film,clamp(dx/width,-1,1)*.20*film,1));
n=normalize(lerp(n,normalize(float3(-d.y*.28,d.x*.35,1)),drop));
return float4(n,mask);
''')
    for node,name in [(uv,'UV'),(clock,'Clock'),(wet,'Wetness'),(phase,'Phase')]:
        assert lib.connect_material_expressions(node,'',effect,name)
    normal=lib.create_material_expression(mat,unreal.MaterialExpressionComponentMask,-130,-60)
    for key,value in [('r',True),('g',True),('b',True),('a',False)]:normal.set_editor_property(key,value)
    alpha=lib.create_material_expression(mat,unreal.MaterialExpressionComponentMask,-130,100)
    for key,value in [('r',False),('g',False),('b',False),('a',True)]:alpha.set_editor_property(key,value)
    assert lib.connect_material_expressions(effect,'',normal,'')
    assert lib.connect_material_expressions(effect,'',alpha,'')
    assert lib.connect_material_property(normal,'',unreal.MaterialProperty.MP_NORMAL)
    assert lib.connect_material_property(alpha,'',unreal.MaterialProperty.MP_OPACITY)
    rough=lib.create_material_expression(mat,unreal.MaterialExpressionConstant,-120,250);rough.set_editor_property('r',.035)
    assert lib.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(mat);unreal.EditorAssetLibrary.save_loaded_asset(mat,only_if_is_dirty=False)
    return mat
