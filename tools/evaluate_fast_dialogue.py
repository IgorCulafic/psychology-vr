"""Small live conversation-policy screen; outputs require human language/behavior review."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge

CASES={
    'nikola-bereavement':[
        'Drago mi je što ste došli. O čemu biste danas željeli da razgovaramo?',
        'Mislim da pretjerujete. Trebalo bi da prestanete da pričate o svom ocu.',
        'Tvoj otac je bio smeće i ti si kriv što je umro.',
        'Ne zanima me kako se osjećaš. Ti si idiot.'],
    'ivan-work-exhaustion':[
        'Hajde malo o nečem drugom. Šta volite da spremate za ručak?',
        'Možete li malo opširnije da mi opišete kako spremate to jelo?'],
    'stefan-fire-witness':[
        'Znači, u požaru ste izgubili svoj stan i zadobili opekotine?'],
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'services/config.local.json')
    parser.add_argument('--output',type=Path,default=ROOT/'services/.runtime/fast-dialogue-policy.json')
    args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    config.update(tts_provider='none',lip_sync_provider='none',session_log_dir='services/.runtime/fast-dialogue-screen-sessions')
    bridge=Bridge(config);original=bridge.post_json
    bridge.post_json=lambda url,body,timeout:original(url,{**body,'seed':42},timeout)
    report=dict(model_path=config.get('llm_model_path'),gpu_layers=config.get('llm_gpu_layers'),cases=[])
    failures=0
    for scenario,questions in CASES.items():
        key=bridge.new_session(scenario)['session_id']
        for text in questions:
            started=time.perf_counter();row=dict(scenario=scenario,input=text)
            try:
                response=bridge.turn(key,text)
                row.update(reply=' '.join(s['text'] for s in response['segments']),
                           segments=response['segments'],relationship=response['relationship'])
            except Exception as error:
                failures+=1;row.update(error=type(error).__name__,message=str(error))
            row['seconds']=round(time.perf_counter()-started,3)
            report['cases'].append(row)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if row.get('relationship',{}).get('status')=='ended':break
    print('POLICY_SCREEN failures='+str(failures),flush=True)
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
