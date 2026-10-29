"""Export native cast meshes, material inputs and baked animations for Unity."""
import json,traceback,re
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/metahuman/exports/unity';OUT.mkdir(parents=True,exist_ok=True)
report={'status':'exporting','characters':[],'materials':{},'textures':{}}
def save(): (OUT/'manifest.json').write_text(json.dumps(report,indent=2))
def export(obj,file,options=None):
    path=OUT/file;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size>0:return
    task=unreal.AssetExportTask();task.object=obj;task.filename=str(path);task.automated=True;task.prompt=False;task.replace_identical=True
    if options:task.options=options
    if not unreal.Exporter.run_asset_export_task(task):raise RuntimeError('Export failed '+str(path)+' '+str(task.errors))
    assert path.exists() and path.stat().st_size>0
def clean(value):return re.sub('[^a-zA-Z0-9_-]','_',value)
def texture(tex):
    import hashlib
    path=tex.get_path_name()
    if path not in report['textures']:
        file='textures/'+clean(tex.get_name())+'_'+hashlib.sha256(path.encode()).hexdigest()[:8]+'.png'
        export(tex,file);report['textures'][path]={'file':file,'srgb':bool(tex.get_editor_property('srgb'))}
    return path
def material(mat):
    if not mat:return None
    if isinstance(mat,unreal.MaterialInstanceDynamic):return material(mat.get_editor_property('parent'))
    key=mat.get_path_name()
    if key in report['materials']:return key
    row={'name':mat.get_name(),'textures':{},'scalars':{},'vectors':{}};report['materials'][key]=row
    lib=unreal.MaterialEditingLibrary
    if isinstance(mat,unreal.MaterialInstanceConstant):
        for param in lib.get_texture_parameter_names(mat):
            tex=lib.get_material_instance_texture_parameter_value(mat,param)
            if not tex or not isinstance(tex,unreal.Texture2D):continue
            row['textures'][str(param)]=texture(tex)
        for param in lib.get_scalar_parameter_names(mat):row['scalars'][str(param)]=lib.get_material_instance_scalar_parameter_value(mat,param)
        for param in lib.get_vector_parameter_names(mat):
            c=lib.get_material_instance_vector_parameter_value(mat,param);row['vectors'][str(param)]=[c.r,c.g,c.b,c.a]
    return key
opts=unreal.FbxExportOption();opts.ascii=False;opts.level_of_detail=False;opts.collision=False;opts.export_morph_targets=True;opts.export_preview_mesh=False
try:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cast=json.loads((ROOT/'experiments/metahuman/cast.json').read_text())['characters']
    for char in cast:
        name=char['asset_name'];row=dict(char,meshes=[],animations=[]);report['characters'].append(row);save()
        bp=unreal.load_asset(f'/Game/MetaHumans/{name}/BP_{name}')
        actor=actors.spawn_actor_from_class(bp.generated_class(),unreal.Vector())
        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
            mesh=component.get_skinned_asset()
            if not mesh:continue
            file=f"{char['id']}/models/{clean(component.get_name())}.fbx";export(mesh,file,opts)
            mats=[material(component.get_material(i)) for i in range(component.get_num_materials())]
            row['meshes'].append({'name':component.get_name(),'asset':mesh.get_path_name(),'file':file,'type':'skeletal','materials':mats})
            save()
        # Cards are the portable counterpart of Unreal-only strand grooms.
        for component in actor.get_components_by_class(unreal.GroomComponent):
            groom=component.get_editor_property('groom_asset')
            if not groom:continue
            cards=list(groom.get_editor_property('hair_groups_cards'))
            is_mesh=False
            if not cards:
                cards=list(groom.get_editor_property('hair_groups_meshes'));is_mesh=True
            if not cards:
                row.setdefault('grooms_without_cards',[]).append(groom.get_path_name());continue
            groups={}
            for card in cards:
                group=int(card.get_editor_property('group_index'));lod=int(card.get_editor_property('lod_index'))
                if group not in groups or lod<groups[group][0]:groups[group]=(lod,card)
            for group,(lod,card) in groups.items():
                mesh=card.get_editor_property('imported_mesh')
                if not mesh:continue
                file=f"{char['id']}/models/{clean(component.get_name())}_cards_{group}.fbx";export(mesh,file,opts)
                mats=[material(m.material_interface) for m in mesh.get_editor_property('static_materials')]
                tx=card.get_editor_property('textures')
                atlas=[texture(t) if t else None for t in tx.get_editor_property('textures')]
                row['meshes'].append({'name':component.get_name()+'_cards_'+str(group),'asset':mesh.get_path_name(),'file':file,'type':'hair_cards','materials':mats,'texture_layout':str(tx.get_editor_property('layout')),'atlas':atlas,'groom_mesh':is_mesh,'card_description':str(card)})
                save()
        actors.destroy_actor(actor)
        # Replacement identities use freshly baked runtime reactions, not the
        # original cast's fixed-sentence audition animations.
        if char.get('animation_key'):continue
        for emotion in ['afraid','crying','angry']:
            if char['id']=='alex':
                package='/Game/Audition/AngerBlend' if emotion=='angry' else '/Game/Audition/Speaking/'+emotion
            else:package=f"/Game/Audition/Cast/{char['id']}/{emotion}"
            variant='shout' if emotion=='angry' else 'emotion'
            for part in ['Face','Body']:
                anim=unreal.load_asset(package+'/AS_'+variant+'_'+part);assert anim
                file=f"{char['id']}/animations/{emotion}_{part.lower()}.fbx";export(anim,file,opts)
                row['animations'].append({'emotion':emotion,'part':part,'file':file,'source':anim.get_path_name()})
        save()
    report['status']='exported'
except Exception:report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:save();unreal.SystemLibrary.quit_editor()
