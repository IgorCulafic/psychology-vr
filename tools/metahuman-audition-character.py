"""Create the isolated male audition character using installed Epic presets."""
import json
from pathlib import Path
import traceback
import sys
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'experiments/metahuman/character-report.json'
report = {'status': 'starting', 'preset': '/MetaHumanCharacter/Optional/Presets/Dominic'}
character = None
subsystem = None

def status(value):
    report['status'] = value
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('MH_CHARACTER ' + value)

try:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    existing_bp = unreal.load_asset('/Game/MetaHumans/AuditionMale/BP_AuditionMale') if unreal.EditorAssetLibrary.does_asset_exist('/Game/MetaHumans/AuditionMale/BP_AuditionMale') else None
    if existing_bp:
        unreal.BlueprintEditorLibrary.compile_blueprint(existing_bp)
        if not existing_bp.generated_class():
            raise RuntimeError('Saved character Blueprint cannot compile')
        unreal.EditorAssetLibrary.save_loaded_asset(existing_bp)
        report['assembled_assets'] = list(unreal.EditorAssetLibrary.list_assets('/Game/MetaHumans', recursive=True))
        report['character'] = '/Game/Characters/AuditionMale.AuditionMale'
        report['reused_saved_assembly'] = True
        status('assembled')
        sys.exit(0)
    destination = '/Game/Characters/AuditionMale'
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        character = unreal.load_asset(destination)
    else:
        character = unreal.EditorAssetLibrary.duplicate_asset(report['preset'], destination)
    if not character:
        raise RuntimeError('Could not create character from Dominic preset')
    report['character'] = character.get_path_name()
    unreal.EditorAssetLibrary.save_loaded_asset(character)
    status('character_saved')
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    if not subsystem.try_add_object_to_edit(character):
        raise RuntimeError('Could not initialize character for editing')
    if not subsystem.can_build_meta_human(character, False):
        status('requesting_full_face_rig')
        params = unreal.MetaHumanCharacterAutoRiggingRequestParams()
        params.blocking = True
        params.report_progress = False
        # UE's shipped example spells this differently from its reflected enum.
        full_rig = next(n for n in dir(unreal.MetaHumanRigType)
                        if n.replace('_', '') == 'JOINTSANDBLENDSHAPES')
        params.rig_type = getattr(unreal.MetaHumanRigType, full_rig)
        subsystem.request_auto_rigging(character, params)
        unreal.EditorAssetLibrary.save_loaded_asset(character)
    status('requesting_textures')
    if not character.has_high_resolution_textures:
        params = unreal.MetaHumanCharacterTextureRequestParams()
        params.blocking = True
        params.report_progress = False
        subsystem.request_texture_sources(character, params)
    report['has_high_resolution_textures'] = character.has_high_resolution_textures
    unreal.EditorAssetLibrary.save_loaded_asset(character)
    if not subsystem.can_build_meta_human(character):
        raise RuntimeError('Character is not ready to assemble; inspect rigging/texture service errors in log')
    status('assembling')
    params = unreal.MetaHumanCharacterEditorBuildParameters()
    params.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
    params.pipeline_quality = unreal.MetaHumanQualityLevel.HIGH
    params.absolute_build_path = '/Game/MetaHumans'
    params.common_folder_path = '/Game/MetaHumans/Common'
    params.enable_wardrobe_item_validation = False
    try:
        subsystem.build_meta_human(character, params)
    except RuntimeError as exc:
        # UE 5.8 can finish assembly while logging stale reroute-link errors
        # during built-in Control Rig migration. Preserve that diagnostic, save
        # generated assets and check the resulting Blueprint before continuing.
        if 'Cannot break link' not in str(exc):
            raise
        report['control_rig_migration_diagnostic'] = str(exc)
    blueprint = unreal.load_asset('/Game/MetaHumans/AuditionMale/BP_AuditionMale')
    if not blueprint:
        raise RuntimeError('Assembly did not produce the expected Blueprint')
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    if not blueprint.generated_class():
        raise RuntimeError('Character Blueprint has no generated class')
    unreal.EditorAssetLibrary.save_directory('/Game/MetaHumans', only_if_is_dirty=True, recursive=True)
    report['assembled_assets'] = list(unreal.EditorAssetLibrary.list_assets('/Game/MetaHumans', recursive=True))
    if not any('/BP_' in a for a in report['assembled_assets']):
        raise RuntimeError('Assembly did not produce a character Blueprint')
    status('assembled')
except Exception:
    report['error'] = traceback.format_exc()
    unreal.log_error(report['error'])
    status('error')
finally:
    if subsystem and character and subsystem.is_object_added_for_editing(character):
        subsystem.remove_object_to_edit(character)
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
