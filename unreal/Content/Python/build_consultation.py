"""Unreal editor Python: import shared art and create an editable consultation map.

Run through tools/build-unreal.ps1. Existing generated assets/maps are preserved;
delete/rename a generated map in the editor deliberately before rebuilding it.
"""
import unreal as u
import json
from pathlib import Path

ROOT = Path(u.Paths.project_dir()).resolve().parent
ART = ROOT / 'unity/Assets/PsychologyVR/Art'
DEST = '/Game/Psychology/Generated'
LIB = u.EditorAssetLibrary
TOOLS = u.AssetToolsHelpers.get_asset_tools()
MEL = u.MaterialEditingLibrary
REPORT = {'assets': [], 'materials': [], 'warnings': []}

def imported(path, folder, name=None, options=None):
    name = name or path.stem
    asset_path = folder + '/' + name
    replace=False
    if LIB.does_asset_exist(asset_path):
        existing=LIB.load_asset(asset_path)
        replace=name=='Jumper' and LIB.get_metadata_tag(existing,'PsychologySeatedExportVersion')!='2'
        if not replace: return existing
    task = u.AssetImportTask()
    for key, value in dict(filename=str(path), destination_path=folder,
        destination_name=name, automated=True, save=True, replace_existing=replace).items():
        task.set_editor_property(key, value)
    if options: task.set_editor_property('options', options)
    TOOLS.import_asset_tasks([task])
    found = [LIB.load_asset(p) for p in task.get_editor_property('imported_object_paths')]
    found = [a for a in found if a]
    if not found: raise RuntimeError('Import failed: ' + str(path))
    REPORT['assets'].extend(a.get_path_name() for a in found)
    return next((a for a in found if isinstance(a,(u.StaticMesh,u.SkeletalMesh,u.Texture2D))),found[0])

def texture(path, kind='color', character=False):
    if not path or not Path(path).is_file(): return None
    tex = imported(Path(path), DEST + ('/Character/Textures' if character else '/Environment/Textures'))
    tex.set_editor_property('max_texture_size', 2048 if character else 1024)
    if kind=='normal':
        tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property('srgb',False)
        tex.set_editor_property('flip_green_channel', not character)
    elif kind=='linear': tex.set_editor_property('srgb',False)
    LIB.save_loaded_asset(tex)
    return tex

def material(name, spec, character=False):
    folder = DEST + ('/Character/Materials' if character else '/Environment/Materials')
    path = folder + '/' + name.replace('.','_')
    if LIB.does_asset_exist(path):
        mat=LIB.load_asset(path)
        if LIB.get_metadata_tag(mat,'PsychologyMaterialVersion')=='2':
            if character:
                MEL.set_material_usage(mat,u.MaterialUsage.MATUSAGE_MORPH_TARGETS)
                MEL.recompile_material(mat); LIB.save_loaded_asset(mat,only_if_is_dirty=False)
            return mat
        MEL.delete_all_material_expressions(mat)
    else: mat = TOOLS.create_asset(path.rsplit('/',1)[1],folder,u.Material,u.MaterialFactoryNew())
    mat.set_editor_property('two_sided',spec.get('doubleSided',False))
    if spec.get('film'): mat.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
    elif spec.get('cutout'): mat.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED)
    def expr(cls): return MEL.create_material_expression(mat,cls)
    def scalar(value, prop):
        e=expr(u.MaterialExpressionConstant); e.set_editor_property('r',float(value)); MEL.connect_material_property(e,'',prop)
    def sample(key,kind):
        source=spec.get(key)
        if not source: return None
        source=Path(source) if character else ROOT/'unity'/source
        tex=texture(source,kind,character)
        if not tex: return None
        e=expr(u.MaterialExpressionTextureSample); e.set_editor_property('texture',tex)
        if kind=='normal': e.set_editor_property('sampler_type',u.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif kind=='linear': e.set_editor_property('sampler_type',u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        return e
    color=spec.get('color',[1,1,1,1]); tint=expr(u.MaterialExpressionConstant3Vector)
    tint.set_editor_property('constant',u.LinearColor(*color[:3],1))
    base=sample('baseMap','color')
    if base:
        multiply=expr(u.MaterialExpressionMultiply)
        MEL.connect_material_expressions(base,'RGB',multiply,'A'); MEL.connect_material_expressions(tint,'',multiply,'B')
        MEL.connect_material_property(multiply,'',u.MaterialProperty.MP_BASE_COLOR)
        if spec.get('cutout') or spec.get('film'):
            MEL.connect_material_property(base,'A',u.MaterialProperty.MP_OPACITY if spec.get('film') else u.MaterialProperty.MP_OPACITY_MASK)
    else: MEL.connect_material_property(tint,'',u.MaterialProperty.MP_BASE_COLOR)
    normal=sample('normalMap','normal')
    if normal: MEL.connect_material_property(normal,'RGB',u.MaterialProperty.MP_NORMAL)
    metal=sample('metalMap','linear')
    if metal:
        MEL.connect_material_property(metal,'R',u.MaterialProperty.MP_METALLIC)
        inv=expr(u.MaterialExpressionOneMinus)
        if not MEL.connect_material_expressions(metal,'A',inv,''): raise RuntimeError('Roughness connection failed: '+name)
        MEL.connect_material_property(inv,'',u.MaterialProperty.MP_ROUGHNESS)
    else:
        scalar(spec.get('metallic',0),u.MaterialProperty.MP_METALLIC)
        scalar(1-spec.get('smoothness',.3),u.MaterialProperty.MP_ROUGHNESS)
    if name=='Room_WindowLight': MEL.connect_material_property(tint,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.set_material_usage(mat,u.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    if character: MEL.set_material_usage(mat,u.MaterialUsage.MATUSAGE_MORPH_TARGETS)
    MEL.recompile_material(mat); LIB.set_metadata_tag(mat,'PsychologyMaterialVersion','2'); LIB.save_loaded_asset(mat)
    REPORT['materials'].append(path)
    return mat

materials={}
for file in ['materials.json','custom-materials.json']:
    for spec in json.loads((ART/'Environment'/file).read_text())['materials']:
        materials[spec['name']]=material(spec['name'],spec)

room={}
for path in sorted((ART/'Environment/Models').glob('*.fbx')):
    options=u.FbxImportUI(); options.set_editor_property('automated_import_should_detect_type',False)
    options.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_STATIC_MESH)
    options.set_editor_property('import_materials',False); options.set_editor_property('import_textures',False)
    data=options.static_mesh_import_data
    data.set_editor_property('combine_meshes',True); data.set_editor_property('generate_lightmap_u_vs',True)
    data.set_editor_property('convert_scene_unit',True)
    mesh=imported(path,DEST+'/Environment/Meshes',options=options)
    slots=mesh.get_editor_property('static_materials')
    for i, slot in enumerate(slots):
        name=str(slot.get_editor_property('imported_material_slot_name'))
        if name in materials: mesh.set_material(i,materials[name])
        else: REPORT['warnings'].append('Unmapped room slot '+path.stem+': '+name)
    LIB.save_loaded_asset(mesh); room[path.stem]=mesh

character_folder=DEST+'/Character'
options=u.FbxImportUI(); options.set_editor_property('automated_import_should_detect_type',False)
options.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_SKELETAL_MESH)
options.set_editor_property('import_as_skeletal',True); options.set_editor_property('import_animations',True)
options.set_editor_property('create_physics_asset',False); options.set_editor_property('import_materials',False); options.set_editor_property('import_textures',False)
options.skeletal_mesh_import_data.set_editor_property('import_morph_targets',True)
options.skeletal_mesh_import_data.set_editor_property('convert_scene_unit',True)
mesh=imported(ROOT/'.cache/unreal/JumperSeated.fbx',character_folder,'Jumper',options)
if not isinstance(mesh,u.SkeletalMesh):
    meshes=[LIB.load_asset(p) for p in LIB.list_assets(character_folder) if isinstance(LIB.load_asset(p),u.SkeletalMesh)]
    if not meshes: raise RuntimeError('No skeletal character imported')
    mesh=meshes[0]
textures=ART/'Characters/Candidates/Jumper/textures'
files=list(textures.iterdir())
character_slots=mesh.get_editor_property('materials')
for i, slot in enumerate(character_slots):
    name=str(slot.get_editor_property('material_slot_name')); prefix=name.removesuffix('_001').removesuffix('.001')
    suffix='_0001' if name.endswith(('_001','.001')) else ''
    def find(stem): return next((p for p in files if p.stem==stem),None)
    rgba=find(prefix+'_RGBA'+suffix); diffuse=rgba or find(prefix+'_Diffuse'+suffix); normal=find(prefix+'_Normal')
    film=rgba and any(n in name for n in ['Cornea','Occlusion','Tearline'])
    spec={'baseMap':str(diffuse) if diffuse else None,'normalMap':str(normal) if normal else None,
        'color':[1,1,1,1],'smoothness':.55 if 'Eye' in name else .25,'doubleSided':True,'cutout':bool(rgba and not film),'film':bool(film)}
    mat=material(name,spec,True)
    slot.set_editor_property('material_interface',mat)
    character_slots[i]=slot
    if not diffuse: REPORT['warnings'].append('No character diffuse: '+name)
mesh.modify()
mesh.materials=character_slots
LIB.set_metadata_tag(mesh,'PsychologySeatedExportVersion','2')
LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
idle_options=u.FbxImportUI()
idle_options.set_editor_property('automated_import_should_detect_type',False)
idle_options.set_editor_property('mesh_type_to_import',u.FBXImportType.FBXIT_ANIMATION)
idle_options.set_editor_property('import_mesh',False)
idle_options.set_editor_property('import_animations',True)
idle_options.set_editor_property('skeleton',mesh.get_editor_property('skeleton'))
idle=imported(ROOT/'.cache/unreal/JumperSeated.fbx',character_folder,'SeatedIdle',idle_options)
animations=[idle]
REPORT['character_mesh']=mesh.get_path_name()
REPORT['animations']=[a.get_path_name() for a in animations]

MAP='/Game/Psychology/Consultation'
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
if not LIB.does_asset_exist(MAP):
    level.new_level(MAP)
    def pos(v): return u.Vector(v[2]*100,v[0]*100,v[1]*100)
    def prop(name,location,yaw=0,scale=(1,1,1)):
        a=actors.spawn_actor_from_class(u.StaticMeshActor,pos(location),u.Rotator(pitch=0,yaw=yaw-90,roll=0))
        a.set_actor_label(name); a.static_mesh_component.set_static_mesh(room[name]); a.set_actor_scale3d(u.Vector(scale[2],scale[0],scale[1])); return a
    prop('consultation_architecture',(0,0,0))
    prop('modern_arm_chair_01',(0,0,1.32),180)
    prop('modern_arm_chair_01',(0,0,-1.67))
    prop('side_table_01',(.95,0,1.15),-12)
    prop('tissue_box',(.94,.553,1.10),-12)
    prop('small_wooden_table_01',(0,0,-.68),0,(1.48,1.39,1.45))
    prop('binder_notebook',(.03,.745,-.84),-9,(.72,.72,.72))
    prop('pencil',(.15,.75,-.70),-10)
    prop('water_cup',(.44,.742,-.56))
    prop('modern_coffee_table_01',(-1.94,0,1.20),90)
    prop('potted_plant_02',(2.12,0,2.30),-30,(1.55,1.55,1.55))
    prop('potted_plant_02',(-2.05,.39,1.40),0,(.6,.6,.6))
    lamp=prop('modern_ceiling_lamp_01',(0,1.99,.45))
    lamp.static_mesh_component.set_cast_shadow(False)
    patient_class=u.load_class(None,'/Script/PsychologyVR.PsychologyPatient')
    patient=actors.spawn_actor_from_class(patient_class,pos((0,0,1.32)),u.Rotator(pitch=0,yaw=90,roll=0))
    patient.set_actor_label('Patient - animation tool integration point')
    body=patient.get_editor_property('body'); body.set_skeletal_mesh_asset(mesh)
    for i,slot in enumerate(character_slots): body.set_material(i,slot.get_editor_property('material_interface'))
    if animations:
        body.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
        data=body.get_editor_property('animation_data'); data.set_editor_property('anim_to_play',animations[0]); data.set_editor_property('saved_looping',True); data.set_editor_property('saved_playing',True); body.set_editor_property('animation_data',data)
    actors.spawn_actor_from_class(u.PlayerStart,pos((0,0,-1.5)),u.Rotator(pitch=0,yaw=0,roll=0))
    for name,location,power,color,shadow in [
        ('Warm ceiling',(0,2.35,.4),1800,(1,.86,.7),True),
        ('Window fill',(2.25,1.95,.5),1400,(.8,.9,1),False),
        ('Reflected light',(0,1.95,-1.8),650,(1,.95,.86),False)]:
        light=actors.spawn_actor_from_class(u.PointLight,pos(location)); light.set_actor_label(name)
        c=light.point_light_component; c.set_mobility(u.ComponentMobility.MOVABLE); c.set_editor_property('intensity_units',u.LightUnits.LUMENS); c.set_intensity(power)
        c.set_light_color(u.LinearColor(*color)); c.set_editor_property('attenuation_radius',700); c.set_cast_shadows(shadow)
    volume=actors.spawn_actor_from_class(u.PostProcessVolume,u.Vector())
    volume.set_actor_label('Consultation exposure'); volume.set_editor_property('unbound',True)
    settings=volume.get_editor_property('settings')
    settings.set_editor_property('override_auto_exposure_method',True)
    settings.set_editor_property('auto_exposure_method',u.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure',True)
    settings.set_editor_property('auto_exposure_apply_physical_camera_exposure',False)
    settings.set_editor_property('override_auto_exposure_bias',True)
    settings.set_editor_property('auto_exposure_bias',-3.0)
    volume.set_editor_property('settings',settings)
    level.save_current_level()
else: REPORT['warnings'].append('Existing consultation map preserved')
LIB.save_directory('/Game/Psychology',only_if_is_dirty=True,recursive=True)
(ROOT/'docs/generated/unreal-import.json').write_text(json.dumps(REPORT,indent=2),encoding='utf-8')
u.log('PSYCHOLOGY_IMPORT_OK '+json.dumps(REPORT))
