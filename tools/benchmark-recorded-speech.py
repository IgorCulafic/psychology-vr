"""Measure recorded/cache preparation only; no dialogue, transcription or playback."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge, validate_reply


def benchmark(config):
    bridge=Bridge(config)
    if not bridge.speech_reuse.cache_enabled or not bridge.speech_reuse.recordings:
        raise ValueError('Run Enable Recorded Speech.cmd first')
    def no_synthesis(*args):
        raise RuntimeError('A recorded clip was unavailable; this probe does not run live TTS')
    bridge.synthesize=no_synthesis
    rows=[]
    for clip in bridge.speech_reuse.recordings.values():
        segment=validate_reply({'segments':[dict(text=clip['text'],emotion=clip['emotion'],intensity=.5)]})[0]
        segment['scenario_id']=clip['scenario_id']
        row=dict(scenario=clip['scenario_id'],emotion=clip['emotion'])
        for trial in ('first_pass','cached'):
            ident=uuid.uuid4().hex;part=dict(segment);start=time.perf_counter()
            try:
                speech,alignment=bridge.prepare_audio_segment(part,ident)
                row[trial]=dict(seconds=round(time.perf_counter()-start,4),source=part['speech_source'],
                    speech_ms=speech,alignment_ms=alignment)
            finally:
                (bridge.runtime/(ident+'.wav')).unlink(missing_ok=True)
        rows.append(row)
    return dict(recorded_clips=len(rows),samples=rows,
        median_cached_speech_stage_seconds=statistics.median(r['cached']['seconds'] for r in rows),
        includes_llm=False,includes_stt=False,includes_playback=False,target_4090_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'services/config.local.json')
    args=parser.parse_args()
    report=benchmark(json.loads(args.config.read_text(encoding='utf-8-sig')))
    output=ROOT/'services/.runtime/recorded-speech-benchmark.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Report: '+str(output))
    print('Median cached speech preparation: '+str(report['median_cached_speech_stage_seconds'])+' seconds')
    print('This excludes dialogue, transcription and actual playback; it is not a 15-second acceptance test.')
