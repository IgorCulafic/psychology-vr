"""Solve approved speech to facial controls locally and export editable tracks."""
import json,time,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman/speaking'
report={'status':'starting','takes':[]}
def save(): (OUT/'solve-report.json').write_text(json.dumps(report,indent=2))
try:
    assets=unreal.AssetToolsHelpers.get_asset_tools()
    bp=unreal.load_asset('/Game/MetaHumans/AuditionMale/BP_AuditionMale')
    for take in json.loads((OUT/'manifest.json').read_text(encoding='utf-8')):
        name=take['name'];package='/Game/Audition/Speaking/'+name
        report['status']='solving_'+name;save()
        task=unreal.AssetImportTask();task.filename=take['audio'];task.destination_path=package;task.destination_name='Speech'
        task.automated=True;task.replace_existing=True;task.save=True
        assets.import_asset_tasks([task])
        audio=unreal.load_asset(package+'/Speech')
        if not audio:raise RuntimeError('Audio import failed: '+name)
        perf=unreal.load_asset(package+'/Performance')
        if not perf:perf=assets.create_asset('Performance',package,unreal.MetaHumanPerformance,unreal.MetaHumanPerformanceFactoryNew())
        perf.set_editor_property('input_type',unreal.DataInputType.AUDIO)
        perf.set_editor_property('audio',audio)
        perf.set_editor_property('realtime_audio',False)
        perf.set_editor_property('audio_driven_animation_output_controls',unreal.AudioDrivenAnimationOutputControls.MOUTH_ONLY)
        perf.set_editor_property('generate_blinks',False)
        perf.set_editor_property('start_frame_to_process',0)
        perf.set_editor_property('end_frame_to_process',take['frames'])
        perf.set_editor_property('visualization_object',unreal.load_asset('/Game/MetaHumans/AuditionMale/Face/SKM_AuditionMale_FaceMesh'))
        perf.set_blocking_processing(True)
        start=time.monotonic();result=perf.start_pipeline()
        if result!=unreal.StartPipelineErrorType.NONE:raise RuntimeError(str(result))
        data=[dict(f.animation_data) for f in perf.get_animation_data()]
        if not data or not any(data):raise RuntimeError('Empty speech solve')
        unreal.EditorAssetLibrary.save_loaded_asset(perf,only_if_is_dirty=False)
        (OUT/(name+'-curves.json')).write_text(json.dumps(data))
        settings=unreal.MetaHumanPerformanceExportLevelSequenceSettings()
        settings.show_export_dialog=False;settings.package_path=package;settings.asset_name='LS_Audio'
        settings.export_video_track=False;settings.export_depth_track=False;settings.export_audio_track=False
        settings.export_image_plane=False;settings.export_identity=False;settings.export_camera=False
        settings.apply_lens_distortion=False;settings.export_control_rig_track=True;settings.target_meta_human_class=bp
        settings.enable_meta_human_head_movement=False
        settings.export_range=unreal.PerformanceExportRange.WHOLE_SEQUENCE
        settings.curve_interpolation=unreal.RichCurveInterpMode.RCIM_LINEAR
        seq=unreal.MetaHumanPerformanceExportUtils.export_level_sequence(perf,settings)
        if not seq:raise RuntimeError('Speech sequence missing')
        unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
        for variant in ['lips','emotion']:
            for prefix in ['LS_','LS_Control_']:
                path=package+'/'+prefix+variant
                if not unreal.EditorAssetLibrary.does_asset_exist(path):
                    copy=unreal.EditorAssetLibrary.duplicate_asset('/Game/Audition/Sequences/LS_Closeup_'+name,path)
                    unreal.EditorAssetLibrary.save_loaded_asset(copy,only_if_is_dirty=False)
        report['takes'].append({'name':name,'frames':len(data),'expected_frames':take['frames'],'seconds':time.monotonic()-start,'sequence':seq.get_path_name()});save()
    report['status']='solved_restart_before_blend'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:save()
