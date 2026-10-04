"""Run via UnrealEditor -ExecutePythonScript; prepares mono performance assets locally."""
import json
from pathlib import Path
import traceback
import unreal

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'experiments/metahuman/prepare-report.json'
report={'status':'starting','performances':[]}
try:
    tools=unreal.AssetToolsHelpers.get_asset_tools()
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    report['character_presets']=[str(a.package_name) for a in registry.get_assets_by_class(
        unreal.TopLevelAssetPath('/Script/MetaHumanCharacter','MetaHumanCharacter'),True)]
    engine=Path(unreal.Paths.engine_dir())
    report['core_data_present']=(engine/'Plugins/MetaHuman/MetaHumanCharacter/Content/Optional').exists()
    for take in json.loads((ROOT/'experiments/metahuman/media/manifest.json').read_text()):
        name=take['name'];package='/Game/Audition/'+name
        def asset(label,cls,factory):
            path=package+'/'+label
            return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else tools.create_asset(label,package,cls,factory)
        media=asset('Video',unreal.ImgMediaSource,unreal.ImgMediaSourceFactoryNew())
        media.set_sequence_path(take['frames_folder'].replace('\\','/'))
        media.set_editor_property('frame_rate_override',unreal.FrameRate(30,1))
        capture=asset('Capture',unreal.FootageCaptureData,unreal.FootageCaptureDataFactory())
        capture.set_editor_property('image_sequences',[media])
        metadata=capture.get_editor_property('metadata')
        metadata.set_editor_property('frame_rate',30.0)
        metadata.set_editor_property('device_model_name','Samsung SM-S928B mono video')
        capture.set_editor_property('metadata',metadata)
        perf=asset('Performance',unreal.MetaHumanPerformance,unreal.MetaHumanPerformanceFactoryNew())
        perf.set_editor_property('input_type',unreal.DataInputType.MONO_FOOTAGE)
        perf.set_editor_property('footage_capture_data',capture)
        perf.set_editor_property('start_frame_to_process',0)
        perf.set_editor_property('end_frame_to_process',take['frames'])
        for obj in [media,capture,perf]:unreal.EditorAssetLibrary.save_loaded_asset(obj)
        row={'name':name,'asset':perf.get_path_name(),'frames':take['frames']}
        report['performances'].append(row)
        unreal.log('MH_AUDITION_PREPARED '+json.dumps(row))
    report['status']='prepared'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('MH_AUDITION_PREPARE_RESULT '+report['status'])
