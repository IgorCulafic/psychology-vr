"""Export solved takes to the assembled male MetaHuman (normal UE editor)."""
import json
from pathlib import Path
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/metahuman'
report = {'status': 'starting', 'sequences': []}
try:
    character_report = json.loads((OUT / 'character-report.json').read_text())
    if character_report['status'] != 'assembled':
        raise RuntimeError('Assemble the audition character before exporting')
    paths = character_report['assembled_assets']
    bp_path = next(p for p in paths if '/BP_AuditionMale.' in p)
    bp = unreal.load_asset(bp_path)
    report['character_blueprint'] = bp_path
    for take in json.loads((OUT / 'media/manifest.json').read_text()):
        name = take['name']
        existing_path = '/Game/Audition/Sequences/LS_Closeup_' + name
        if unreal.EditorAssetLibrary.does_asset_exist(existing_path):
            sequence = unreal.load_asset(existing_path)
            if not sequence.get_bindings():
                raise RuntimeError('Saved sequence has no bindings: ' + existing_path)
            report['sequences'].append({'name': name, 'asset': sequence.get_path_name(),
                                        'frames': take['frames']})
            continue
        performance = unreal.load_asset('/Game/Audition/' + name + '/Performance')
        performance.set_editor_property('visualization_object', unreal.load_asset('/Game/MetaHumans/AuditionMale/Face/SKM_AuditionMale_FaceMesh'))
        unreal.EditorAssetLibrary.save_loaded_asset(performance)
        settings = unreal.MetaHumanPerformanceExportLevelSequenceSettings()
        settings.show_export_dialog = False
        settings.package_path = '/Game/Audition/Sequences'
        settings.asset_name = 'LS_Closeup_' + name
        settings.export_video_track = False
        settings.export_depth_track = False
        settings.export_audio_track = False
        settings.export_image_plane = False
        settings.export_identity = False
        settings.export_camera = False
        settings.apply_lens_distortion = False
        settings.export_control_rig_track = True
        settings.target_meta_human_class = bp
        settings.enable_meta_human_head_movement = True
        settings.export_range = unreal.PerformanceExportRange.WHOLE_SEQUENCE
        settings.curve_interpolation = unreal.RichCurveInterpMode.RCIM_LINEAR
        sequence = unreal.MetaHumanPerformanceExportUtils.export_level_sequence(performance, settings)
        if not sequence:
            raise RuntimeError('Level sequence export failed: ' + name)
        # Fixed studio camera avoids footage-calibration assumptions for mono.
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        camera_actor = actors.spawn_actor_from_class(unreal.CineCameraActor,
            unreal.Vector(-90, 0, 160), unreal.Rotator(0, 0, 0))
        camera = camera_actor.get_cine_camera_component()
        filmback = camera.get_editor_property('filmback')
        filmback.sensor_width = 36.0
        filmback.sensor_height = 36.0
        camera.set_editor_property('filmback', filmback)
        camera.set_editor_property('current_focal_length', 120.0)
        camera.set_editor_property('current_aperture', 16.0)
        focus = camera.get_editor_property('focus_settings')
        focus.manual_focus_distance = 140.0
        camera.set_editor_property('focus_settings', focus)
        camera_binding = sequence.add_spawnable_from_instance(camera_actor)
        cut = sequence.add_track(unreal.MovieSceneCameraCutTrack).add_section()
        cut.set_range(0, take['frames'])
        binding_id = unreal.MovieSceneObjectBindingID()
        binding_id.set_editor_property('guid', camera_binding.get_id())
        cut.set_camera_binding_id(binding_id)
        actors.destroy_actor(camera_actor)
        unreal.EditorAssetLibrary.save_loaded_asset(sequence)
        report['sequences'].append({'name': name, 'asset': sequence.get_path_name(),
                                    'frames': take['frames']})
    report['status'] = 'exported_not_rendered'
except Exception:
    report['status'] = 'error'
    report['error'] = traceback.format_exc()
    unreal.log_error(report['error'])
finally:
    (OUT / 'export-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('MH_EXPORT ' + report['status'])
