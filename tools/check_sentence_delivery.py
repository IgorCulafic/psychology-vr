"""Measure real BF16 sentence readiness and prepare labelled emotional review clips.

These are authored comparison lines through the production speech/stream pipeline,
not an assessment of model-selected feelings or human listening quality.
"""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge


def main():
    config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
    if config.get('higgs_quantization','bf16')!='bf16' or config['tts_provider']!='higgs':
        raise RuntimeError('This check requires the selected BF16 Higgs setup')
    config.update(dialogue_provider='scripted',session_log_dir='services/.runtime/sentence-review/logs')
    bridge=Bridge(config)
    output=ROOT/'services/.runtime/sentence-review';output.mkdir(parents=True,exist_ok=True)
    cases=[
        ('restrained-to-confrontation',[
            ('frustrated',.6,'tense','Teško mi je kad me prekidate. Želim da završim ono što sam počeo.'),
            ('angry',.8,'tense','Nemojte tako da govorite o mojoj porodici. To me stvarno vrijeđa.')]),
        ('grief-to-withdrawal',[
            ('sad',.65,'subdued','Nedostaje mi ono što smo imali. Ponekad mi običan razgovor vrati ta sjećanja.'),
            ('despondent',.7,'subdued','Sada nemam snage da pričam o tome. Možemo li malo da ćutimo?')]),
        ('unease-to-fear',[
            ('anxious',.45,'normal','Nijesam očekivao da će mi biti ovako teško. Treba mi trenutak da saberem misli.'),
            ('afraid',.75,'tense','Plašim se da će se ponoviti. Možete li ostati ovdje sa mnom?')]),
    ]
    report={'source':'authored-comparison-through-production-bf16','turns':[],'measurements':[]}
    for name,beats in cases:
        key=bridge.new_session()['session_id']
        planned=[dict(text=text,emotion=emotion,intensity=intensity,gesture='none',voice_style=style,
                      transition_seconds=1.,hold_after_seconds=.2) for emotion,intensity,style,text in beats]
        bridge.generate=lambda *args:planned
        turn=bridge.start_stream(key,'Authored emotional review')['turn_id']
        deadline=time.monotonic()+240
        while True:
            status=bridge.poll_stream(key,turn)
            if status['done']:break
            if time.monotonic()>deadline:raise TimeoutError('Speech review timed out')
            time.sleep(.1)
        if status['error']:raise RuntimeError(status['error'])
        elapsed=round((time.perf_counter()-bridge.sessions[key].stream['started'])*1000)
        entry=dict(name=name,first_ready_ms=status['first_audio_ms'],all_ready_ms=elapsed,
                   sentence_count=len(status['segments']),audio_seconds=sum(s.get('audio_duration_seconds',0) for s in status['segments']))
        report['measurements'].append(entry)
        report['turns'].append(dict(name=name,source='authored-bf16-comparison',reply=dict(segments=status['segments'])))
        # This tool prepares clips; it does not claim to have played or heard them.
        bridge.finish_stream(key,turn,0,reason='audition_prepared_only')
        (output/'replies.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(entry),flush=True)
    print('SENTENCE_REVIEW_READY',output/'replies.json',flush=True)


if __name__=='__main__':main()
