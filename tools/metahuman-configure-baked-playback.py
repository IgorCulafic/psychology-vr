import json
from pathlib import Path
import unreal
root=Path(__file__).resolve().parents[1]/'experiments/metahuman'
report=json.loads((root/'reactions-report.json').read_text())
for take in report['reactions']:
    for clip in take['clips']:
        anim=unreal.load_asset(clip['asset'])
        part=clip['part']
        mesh=unreal.load_asset('/Game/MetaHumans/AuditionMale/'+part+'/SKM_AuditionMale_'+part+'Mesh')
        anim.set_retarget_source_asset(mesh)
        unreal.EditorAssetLibrary.save_loaded_asset(anim,only_if_is_dirty=False)
        task=unreal.AssetExportTask();task.object=anim;task.filename=str(root/'exports/reactions'/clip['file'])
        task.automated=True;task.prompt=False;task.replace_identical=True
        options=unreal.FbxExportOption();options.ascii=False;options.export_preview_mesh=False;task.options=options
        if not unreal.Exporter.run_asset_export_task(task):raise RuntimeError('FBX export failed: '+clip['file'])
        clip['bytes']=Path(task.filename).stat().st_size
    seq=unreal.load_asset(take['sequence'])
    seq.modify()
    for binding in seq.get_bindings():
        for track in binding.get_tracks():
            if isinstance(track,unreal.MovieSceneBoolTrack) and str(binding.get_display_name())=='Body':
                for section in track.get_sections():
                    section.modify()
                    section.get_all_channels()[0].set_default(False)
            if isinstance(track,unreal.MovieSceneSkeletalAnimationTrack):
                for section in track.get_sections():
                    section.modify()
                    params=section.get_editor_property('params')
                    params.set_editor_property('force_custom_mode',True)
                    section.set_editor_property('params',params)
                    assert section.get_editor_property('params').force_custom_mode
    unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
(root/'reactions-report.json').write_text(json.dumps(report,indent=2))
