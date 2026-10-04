"""Assemble the local four-man audition cast. Presets stay unmodified."""
import json, traceback
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]/'experiments/metahuman'
OUT=ROOT/'cast';OUT.mkdir(exist_ok=True)
report={'status':'starting','characters':[]}
sub=unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
def save(): (OUT/'assembly-report.json').write_text(json.dumps(report,indent=2))
try:
    unreal.AssetRegistryHelpers.get_asset_registry().search_all_assets(True)
    for item in json.loads((ROOT/'cast.json').read_text())['characters']:
        name=item['asset_name'];bp_path=f'/Game/MetaHumans/{name}/BP_{name}'
        row=dict(item,blueprint=bp_path,status='starting');report['characters'].append(row);save()
        if unreal.EditorAssetLibrary.does_asset_exist(bp_path):
            bp=unreal.load_asset(bp_path);unreal.BlueprintEditorLibrary.compile_blueprint(bp)
            assert bp.generated_class();row['status']='assembled_existing';save();continue
        path='/Game/Characters/'+name
        character=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/MetaHumanCharacter/Optional/Presets/'+item['preset'],path)
        assert character, path
        unreal.EditorAssetLibrary.save_loaded_asset(character,only_if_is_dirty=False)
        try:
            assert sub.try_add_object_to_edit(character)
            if not sub.can_build_meta_human(character,False):
                row['status']='requesting_rig';save()
                params=unreal.MetaHumanCharacterAutoRiggingRequestParams();params.blocking=True;params.report_progress=False
                params.rig_type=getattr(unreal.MetaHumanRigType,next(n for n in dir(unreal.MetaHumanRigType) if n.replace('_','')=='JOINTSANDBLENDSHAPES'))
                sub.request_auto_rigging(character,params)
                unreal.EditorAssetLibrary.save_loaded_asset(character,only_if_is_dirty=False)
            if not character.has_high_resolution_textures:
                row['status']='requesting_textures';save()
                params=unreal.MetaHumanCharacterTextureRequestParams();params.blocking=True;params.report_progress=False
                sub.request_texture_sources(character,params)
                unreal.EditorAssetLibrary.save_loaded_asset(character,only_if_is_dirty=False)
            if not sub.can_build_meta_human(character): raise RuntimeError('Rig/texture request did not make '+name+' ready to assemble')
            row['status']='assembling';save()
            params=unreal.MetaHumanCharacterEditorBuildParameters()
            params.pipeline_type=unreal.MetaHumanDefaultPipelineType.OPTIMIZED;params.pipeline_quality=unreal.MetaHumanQualityLevel.HIGH
            params.absolute_build_path='/Game/MetaHumans';params.common_folder_path='/Game/MetaHumans/Common';params.enable_wardrobe_item_validation=False
            try: sub.build_meta_human(character,params)
            except RuntimeError as exc:
                if 'Cannot break link' not in str(exc):raise
                row['rig_migration_diagnostic']=str(exc)
            bp=unreal.load_asset(bp_path);assert bp,bp_path
            unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert bp.generated_class()
            unreal.EditorAssetLibrary.save_directory('/Game/MetaHumans',only_if_is_dirty=True,recursive=True)
            row['status']='assembled';save()
        finally:
            if sub.is_object_added_for_editing(character): sub.remove_object_to_edit(character)
    report['status']='assembled'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    save()
    unreal.SystemLibrary.quit_editor()
