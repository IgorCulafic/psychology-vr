"""Compare baseline/optimized BF16 speech using identical text, references and seeds.

Run with other GPU models stopped. These are voice-only results, not reply latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import validate_reply
from higgs_service import HiggsVoice
from higgs_decode import HiggsDecoder
from speech_reuse import wav_duration

SAMPLES=[('alex-earthquake','anxious','Još osjećam strah. Teško mi je da govorim o tome.'),
         ('ivan-work-exhaustion','angry','Stalno traže više od mene. Umoran sam od svega.'),
         ('stefan-fire-witness','sad','Ne znam kako da objasnim taj osjećaj. Sve mi se vraća.'),
         ('nikola-bereavement','sad','Nedostaje mi svaki dan. Ponekad samo želim da budem sam.')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'services/config.local.json')
    parser.add_argument('--output',type=Path,default=ROOT/'services/.runtime/higgs-comparison')
    parser.add_argument('--repeats',type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.repeats<=5:parser.error('--repeats must be 1-5')
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    if config.get('higgs_quantization','bf16')!='bf16':parser.error('This comparison requires BF16 speech')
    config.update(higgs_fast_decode=False,higgs_prepare_openings=False)
    args.output.mkdir(parents=True,exist_ok=True)
    report=dict(samples=[],precision='bf16',includes_llm=False,includes_stt=False,includes_playback=False,
        sentence_streaming=config.get('higgs_sentence_streaming',False),
        limitations=['A matched WAV hash checks output parity for this sample, not all future text.',
                     'Each voice is warmed before its measured baseline/optimized pairs.'])
    try:report['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],text=True).strip()
    except (OSError,subprocess.SubprocessError):report['gpu']='unavailable'
    start=time.perf_counter();voice=HiggsVoice(config)
    report['load_seconds']=round(time.perf_counter()-start,3)
    decoder=HiggsDecoder(voice.model)
    for scenario,emotion,text in SAMPLES:
        segment=validate_reply({'segments':[dict(text=text,emotion=emotion,intensity=.6)]})[0]
        try:
            voice.decoder=None
            voice.synthesize(segment,scenario)  # Excluded kernel/reference warm-up.
            for repeat in range(args.repeats):
                row=dict(scenario=scenario,emotion=emotion,repeat=repeat)
                # Alternate order to avoid attributing progressive warm-up to the adapter.
                order=('baseline','optimized') if repeat%2==0 else ('optimized','baseline')
                for mode in order:
                    voice.decoder=decoder if mode=='optimized' else None
                    start=time.perf_counter();audio=voice.synthesize(segment,scenario)
                    row[mode]=dict(seconds=round(time.perf_counter()-start,3),audio_seconds=wav_duration(audio),
                                   sha256=hashlib.sha256(audio).hexdigest())
                    (args.output/f'{scenario}-{repeat}-{mode}.wav').write_bytes(audio)
                row['identical_wav']=row['baseline']['sha256']==row['optimized']['sha256']
                report['samples'].append(row)
                print(json.dumps(row),flush=True)
        except Exception as exc:
            report['samples'].append(dict(scenario=scenario,error_type=type(exc).__name__,error=str(exc)))
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    report['all_samples_identical']=(len(report['samples'])==len(SAMPLES)*args.repeats and
                                    all(r.get('identical_wav') for r in report['samples']))
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Report:',args.output/'report.json')
    if not report['all_samples_identical']:raise SystemExit(1)


if __name__=='__main__':main()
