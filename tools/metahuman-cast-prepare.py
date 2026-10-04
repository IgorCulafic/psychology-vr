"""Export identity-specific Control Rigs before the fresh-editor speech bake."""
import json,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]/'experiments/metahuman';OUT=ROOT/'cast'
report={'status':'starting','sequences':[]}
try:
    assert json.loads((OUT/'assembly-report.json').read_text())['status']=='assembled'
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    manifest=[]
    for char in json.loads((ROOT/'cast.json').read_text())['characters']:
        if char['id']=='alex':continue # The approved original already has these bakes.
        name=char['asset_name'];bp=unreal.load_asset(f'/Game/MetaHumans/{name}/BP_{name}')
        for take in json.loads((ROOT/'speaking/manifest.json').read_text(encoding='utf-8')):
            mood=take['name'];variant='shout' if mood=='angry' else 'emotion'
            package=f"/Game/Audition/Cast/{char.get('animation_key',char['id'])}/{mood}"
            path=package+'/LS_Control_'+variant
            if not unreal.EditorAssetLibrary.does_asset_exist(path):
                perf=unreal.load_asset('/Game/Audition/'+mood+'/Performance')
                settings=unreal.MetaHumanPerformanceExportLevelSequenceSettings()
                settings.show_export_dialog=False;settings.package_path=package;settings.asset_name='LS_Control_'+variant
                for prop in ['export_video_track','export_depth_track','export_audio_track','export_image_plane','export_identity','export_camera','apply_lens_distortion']:
                    settings.set_editor_property(prop,False)
                settings.export_control_rig_track=True;settings.target_meta_human_class=bp;settings.enable_meta_human_head_movement=True
                settings.export_range=unreal.PerformanceExportRange.WHOLE_SEQUENCE
                settings.curve_interpolation=unreal.RichCurveInterpMode.RCIM_LINEAR
                seq=unreal.MetaHumanPerformanceExportUtils.export_level_sequence(perf,settings);assert seq
                # All presets use the same closeup framing; verify this in the renders.
                camera_actor=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(-90,0,160),unreal.Rotator())
                camera=camera_actor.get_cine_camera_component();filmback=camera.get_editor_property('filmback')
                filmback.sensor_width=36.;filmback.sensor_height=36.;camera.set_editor_property('filmback',filmback)
                camera.set_editor_property('current_focal_length',120.);camera.set_editor_property('current_aperture',16.)
                focus=camera.get_editor_property('focus_settings');focus.manual_focus_distance=140.;camera.set_editor_property('focus_settings',focus)
                binding=seq.add_spawnable_from_instance(camera_actor)
                cut=seq.add_track(unreal.MovieSceneCameraCutTrack).add_section();cut.set_range(0,take['frames'])
                bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',binding.get_id());cut.set_camera_binding_id(bid)
                actors.destroy_actor(camera_actor);unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
            if not unreal.EditorAssetLibrary.does_asset_exist(package+'/LS_'+variant):
                seq=unreal.EditorAssetLibrary.duplicate_asset(path,package+'/LS_'+variant)
                unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
            manifest.append(dict(take,character=char,package=package))
            report['sequences'].append(path)
            (OUT/'prepare-report.json').write_text(json.dumps(report,indent=2))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    report['status']='prepared_restart_before_bake'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    (OUT/'prepare-report.json').write_text(json.dumps(report,indent=2))
    unreal.SystemLibrary.quit_editor()
