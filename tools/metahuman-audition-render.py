"""Render exported MetaHuman auditions with a fixed studio lighting setup."""
import json
from pathlib import Path
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/metahuman'
REACTIONS = '-mhreactions' in unreal.SystemLibrary.get_command_line().lower()
SPEAKING = '-mhspeaking' in unreal.SystemLibrary.get_command_line().lower()
ANGER = '-mhangerblend' in unreal.SystemLibrary.get_command_line().lower()
CAST = '-mhcast' in unreal.SystemLibrary.get_command_line().lower()
TEARS = '-mhtears' in unreal.SystemLibrary.get_command_line().lower()
REPORT_PATH = OUT / ('tears/render-report.json' if TEARS else ('cast/render-report.json' if CAST else ('anger-blend/render-report.json' if ANGER else ('speaking/render-report.json' if SPEAKING else ('reaction-render-report.json' if REACTIONS else 'render-report.json')))))
report = {'status': 'starting'}
executor = None

def write_status(value):
    report['status'] = value
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('MH_RENDER ' + value)

def finished(executor_instance, success):
    report['success'] = success
    write_status('rendered' if success else 'error')
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    unreal.SystemLibrary.quit_editor()

def failed(executor_instance, pipeline, fatal, message):
    report.setdefault('errors', []).append(str(message))
    write_status('rendering_with_error' if not fatal else 'error')

try:
    exports = json.loads((OUT / 'export-report.json').read_text())
    if SPEAKING:
        exports = json.loads((OUT / 'speaking/build-report.json').read_text())
    if ANGER:
        exports = json.loads((OUT / 'anger-blend/build-report.json').read_text())
    if CAST or TEARS:
        exports = json.loads((OUT / ('tears' if TEARS else 'cast') / 'build-report.json').read_text())
    if REACTIONS:
        reactions = json.loads((OUT / 'reactions-report.json').read_text())
        if reactions['status'] != 'baked_and_exported':
            raise RuntimeError('Finish the reaction bake before rendering')
        exports = {'status': 'exported_not_rendered', 'sequences': [
            {'name': r['name'], 'asset': r['sequence'], 'frames': r['source_frames']} for r in reactions['reactions']]}
    if exports['status'] != 'exported_not_rendered':
        raise RuntimeError('Export the performances before rendering')
    # Small frame range for lighting/framing verification before the full run.
    preview = (OUT / 'preview-only.flag').exists()
    report['preview_only'] = preview
    level_path = '/Game/Audition/Studio'
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
        levels.new_level(level_path)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for label, rotation, intensity, color in [
            ('Key', unreal.Rotator(-25, 30, 0), 6.0, unreal.LinearColor(1, .92, .85, 1)),
            ('Fill', unreal.Rotator(-10, -45, 0), 2.5, unreal.LinearColor(.85, .92, 1, 1)),
            ('Rim', unreal.Rotator(-25, 165, 0), 4.0, unreal.LinearColor(1, 1, 1, 1)),
        ]:
            light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 250), rotation)
            light.set_actor_label(label)
            component = light.get_component_by_class(unreal.DirectionalLightComponent)
            component.set_intensity(intensity)
            component.set_light_color(color)
            component.set_mobility(unreal.ComponentMobility.MOVABLE)
        volume = actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector())
        volume.set_editor_property('unbound', True)
        settings = volume.get_editor_property('settings')
        for prop, value in [('auto_exposure_min_brightness', 0.0),
                            ('auto_exposure_max_brightness', 0.0),
                            ('auto_exposure_bias', 0.0), ('motion_blur_amount', 0.0)]:
            settings.set_editor_property('override_' + prop, True)
            settings.set_editor_property(prop, value)
        volume.set_editor_property('settings', settings)
        levels.save_current_level()
    else:
        levels.load_level(level_path)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.PostProcessVolume):
            settings = actor.get_editor_property('settings')
            settings.set_editor_property('override_auto_exposure_method', True)
            settings.set_editor_property('auto_exposure_method', unreal.AutoExposureMethod.AEM_MANUAL)
            settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure', True)
            settings.set_editor_property('auto_exposure_apply_physical_camera_exposure', False)
            settings.set_editor_property('override_auto_exposure_bias', True)
            settings.set_editor_property('auto_exposure_bias', 0.0)
            actor.set_editor_property('settings', settings)
    levels.save_current_level()
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    queue = subsystem.get_queue()
    queue.delete_all_jobs()
    for item in exports['sequences']:
        if preview and item['name'] != 'afraid':
            continue
        job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        job.job_name = item['name']
        job.map = unreal.SoftObjectPath(level_path + '.Studio')
        job.sequence = unreal.SoftObjectPath(item['asset'])
        config = job.get_configuration()
        output = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        output.output_directory = unreal.DirectoryPath(str(OUT / ('anger-blend' if ANGER else 'speaking') / item['name'] / 'render') if SPEAKING or ANGER else str(OUT / 'media' / item['name'] / ('neck-render' if REACTIONS else ('preview' if preview else 'render'))))
        if CAST or TEARS:
            output.output_directory = unreal.DirectoryPath(str(OUT / ('tears' if TEARS else 'cast') / item['name'] / 'render'))
        output.output_resolution = unreal.IntPoint(720, 720)
        output.file_name_format = '{frame_number}'
        output.zero_pad_frame_numbers = 6
        output.override_existing_output = True
        output.use_custom_frame_rate = True
        output.output_frame_rate = unreal.FrameRate(30, 1)
        output.use_custom_playback_range = True
        output.custom_start_frame = 150 if preview else 0
        output.custom_end_frame = 153 if preview else item['frames']
        config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
        camera_settings = config.find_or_add_setting_by_class(unreal.MoviePipelineCameraSetting)
        camera_settings.shutter_timing = unreal.MoviePipelineShutterTiming.FRAME_OPEN
        aa = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.spatial_sample_count = 1
        aa.temporal_sample_count = 1
        aa.engine_warm_up_count = 32
        aa.render_warm_up_count = 16
    executor = unreal.MoviePipelinePIEExecutor(subsystem)
    executor.on_executor_finished_delegate.add_callable_unique(finished)
    executor.on_executor_errored_delegate.add_callable_unique(failed)
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    write_status('rendering')
    subsystem.render_queue_with_executor_instance(executor)
except Exception:
    report['error'] = traceback.format_exc()
    unreal.log_error(report['error'])
    write_status('error')
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
