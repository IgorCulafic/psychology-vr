"""Solve prepared mono footage in MetaHuman Animator locally; retain curves for audit."""
import json
from pathlib import Path
import time
import traceback
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman'
report={'status':'running','takes':[]}
try:
    manifest=json.loads((OUT/'media/manifest.json').read_text())
    for take in manifest:
        name=take['name'];start=time.monotonic()
        perf=unreal.load_asset('/Game/Audition/'+name+'/Performance')
        if not perf:raise RuntimeError('Prepared performance asset missing: '+name)
        perf.set_blocking_processing(True)
        result=perf.start_pipeline()
        if result!=unreal.StartPipelineErrorType.NONE:raise RuntimeError(name+': start_pipeline returned '+str(result))
        data=perf.get_animation_data()
        frames=[dict(frame.animation_data) for frame in data]
        populated=sum(bool(frame) for frame in frames)
        if not populated:raise RuntimeError(name+': solve returned no facial curves')
        unreal.EditorAssetLibrary.save_loaded_asset(perf)
        (OUT/'media'/name/'metahuman-curves.json').write_text(json.dumps({
            'method':'MetaHuman Animator mono video, local UE5.8 processing',
            'source_sha256':take['source_sha256'],'fps':take['fps'],'frames':frames}),encoding='utf-8')
        row={'name':name,'frames':len(frames),'populated_frames':populated,
             'expected_frames':take['frames'],'reported_processed_frames':perf.get_number_of_processed_frames(),
             'seconds':round(time.monotonic()-start,2)}
        report['takes'].append(row)
        (OUT/'solve-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        unreal.log('MH_AUDITION_SOLVED '+json.dumps(row))
    report['status']='solved_curves_only_not_rendered'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    (OUT/'solve-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('MH_AUDITION_SOLVE_RESULT '+report['status'])
