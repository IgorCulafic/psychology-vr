"""Measure first prepared speech and predicted later gaps; playback is a separate check."""
import argparse
import base64
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge
from inference_runtime import config_signature
from latency_metrics import playback_schedule


def percentile(values,p):
    values=sorted(values);position=(len(values)-1)*p
    low=int(position);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(position-low)


def check_workers(config):
    """A stale worker must not masquerade as the requested profile."""
    def health(url):
        parts=urllib.parse.urlsplit(url)
        endpoint=urllib.parse.urlunsplit((parts.scheme,parts.netloc,'/health','',''))
        with urllib.request.urlopen(endpoint,timeout=5) as response:return json.load(response)
    health(config['llm_url'])
    if config.get('tts_provider')=='higgs':
        result=health(config.get('higgs_url','http://127.0.0.1:8766/synthesize'))
        if result.get('config_signature')!=config_signature(config):
            raise ValueError('Higgs worker uses different settings. Stop services and restart with this configuration.')


def benchmark(config,output,turns=8,audio=None,target_seconds=14):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    config=dict(config,session_log_dir=str(output/'sessions'))
    bridge=Bridge(config)
    prompts=['Kako se osjećate sada?','Šta vam je danas bilo najteže?',
             'Možete li mi dati jedan konkretan primjer?','Možemo da usporimo. Šta bi vam sada pomoglo?']
    if config.get('conversation_language')!='cnr':
        prompts=['How are you feeling right now?','What was hardest today?',
                 'Could you give me one concrete example?','We can slow down. What might help now?']
    report=dict(samples=[],target_seconds=target_seconds,includes_stt=audio is not None,
        includes_playback=False,end_to_end_target_verified=False,
        settings={k:config.get(k) for k in ('dialogue_model','llm_gpu_layers','conversation_language',
            'higgs_quantization','higgs_fast_decode','higgs_sentence_streaming','higgs_release_unused_vram',
            'speech_cache_enabled','recorded_speech_enabled','lip_sync_provider',
            'stt_device','stt_model','stt_beam_size','llm_ordinary_word_limit')},
        limitations=['First prepared speech is measured, not audible playback.',
            'Microphone endpointing, WAV transport and game playback are excluded.',
            'Later gaps are predictions with instantaneous WAV download, not measured playback.',
            'Each sample uses an isolated synthetic session. The first sample may warm kernels/prompt slots.',
            'Fixed openings are excluded. Full conversation/history and VR require testing in the game.'])
    def save():
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        report['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],text=True).strip()
    except (OSError,subprocess.SubprocessError):report['gpu']='unavailable'
    save()
    warm_start=time.perf_counter()
    bridge.prepare_speech()
    report['bridge_warmup_seconds']=round(time.perf_counter()-warm_start,3)
    scenarios=list(bridge.profiles)
    for index in range(turns):
        scenario=scenarios[index%len(scenarios)]
        key=bridge.new_session(scenario)['session_id']
        prompt=prompts[(index//len(scenarios))%len(prompts)]
        bridge.last_inference_metrics=[]
        start=time.perf_counter();stt_seconds=0.;turn=None
        row=dict(scenario=scenario,sample_index=index,cold_sample=index==0)
        report['samples'].append(row)
        try:
            if audio:
                prompt=bridge.transcribe(base64.b64encode(audio.read_bytes()).decode())['text']
                stt_seconds=time.perf_counter()-start
                if not prompt:raise ValueError('No speech recognized in benchmark WAV')
            turn=bridge.start_stream(key,prompt)['turn_id'];first=None
            deadline=time.perf_counter()+300
            while time.perf_counter()<deadline:
                status=bridge.poll_stream(key,turn)
                if status['segments'] and first is None:first=time.perf_counter()-start
                if status['done']:break
                time.sleep(.02)
            else:raise TimeoutError('Reply preparation exceeded 300 seconds')
            if status['error']:raise RuntimeError(status['error'])
            if first is None:raise RuntimeError('No speech segment was prepared')
            if not all(s.get('audio_url') for s in status['segments']):
                raise RuntimeError('Speech is disabled or a segment has no audio; latency cannot be measured')
            row.update(first_prepared_seconds=round(first,3),
                complete_preparation_seconds=round(time.perf_counter()-start,3),
                stt_seconds=round(stt_seconds,3),inference=bridge.last_inference_metrics[:],
                segment_schedule=playback_schedule(status['segments']),
                spoken_words=sum(len(s['text'].split()) for s in status['segments']))
        except Exception as exc:
            row.update(error_type=type(exc).__name__,error=str(exc),elapsed_seconds=round(time.perf_counter()-start,3))
        finally:
            # No audio was played. Never commit generated words as heard.
            if turn:bridge.finish_stream(key,turn,0,0,'benchmark_without_playback')
            save()
        print(json.dumps(row,ensure_ascii=True),flush=True)
        if 'error' in row:break
    values=[r['first_prepared_seconds'] for r in report['samples'] if 'first_prepared_seconds' in r]
    waits=[s['extra_preparation_wait_seconds'] for r in report['samples'] for s in r.get('segment_schedule',[])]
    report.update(completed=len(values)==turns,median_seconds=statistics.median(values) if values else None,
        p90_seconds=round(percentile(values,.9),3) if values else None,
        max_seconds=max(values,default=None),max_predicted_extra_gap_seconds=max(waits,default=None),
        preparation_target_met=len(values)==turns and all(v<=target_seconds for v in values))
    save()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'services/config.local.json')
    parser.add_argument('--output',type=Path,default=ROOT/'services/.runtime/response-benchmark')
    parser.add_argument('--turns',type=int,default=8)
    parser.add_argument('--target-seconds',type=float,default=14)
    parser.add_argument('--audio',type=Path,help='Optional mono PCM16 WAV, .2-45 s, to include transcription')
    args=parser.parse_args()
    if not 4<=args.turns<=40:parser.error('--turns must be 4-40')
    if not 1<=args.target_seconds<=120:parser.error('--target-seconds must be 1-120')
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    check_workers(config)
    report=benchmark(config,args.output,args.turns,args.audio,args.target_seconds)
    print('Prepared-speech summary:',json.dumps({k:report[k] for k in
        ('completed','median_seconds','p90_seconds','max_seconds','max_predicted_extra_gap_seconds','preparation_target_met')}))
    print('Report:',args.output/'report.json')
    print('Verify release-to-audible speech and later gaps in the actual game. This benchmark cannot certify end-to-end latency.')
    if not report['completed']:raise SystemExit(1)


if __name__=='__main__':main()
