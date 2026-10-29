"""Live text-only regression against the selected local model; no speech generation.

Compare the saved previous prompt with the current production prompt using the
same seeds. Outputs need human language/role assessment, not keyword-only scores.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
import conversation_prompt
from alex_service import Bridge

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--previous',type=Path)
parser.add_argument('--seeds',type=int,nargs='+',default=[42,43,44])
parser.add_argument('--temperature',type=float)
parser.add_argument('--output',type=Path,default=ROOT/'experiments/dialogue-naturalness/results.json')
args=parser.parse_args()
current=conversation_prompt.PATIENT_CNR_GUIDANCE
variants=[('current',current)]
if args.previous:
    spec=importlib.util.spec_from_file_location('previous_prompt',args.previous)
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    variants.insert(0,('previous',previous.PATIENT_CNR_GUIDANCE))
config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
config.update(tts_provider='none',lip_sync_provider='none',conversation_language='cnr',
    session_log_dir='experiments/dialogue-naturalness/session-logs')
prompts=['I za što je to tako?', 'Šta si radio za vikend?',
    'Šta voliš da kuvaš? Opiši mi malo kako to spremaš.',
    'Znači znaš da je to burnout i znaš kako da ga izliječiš?',
    'Samo si lijen, nemaš ti nikakav problem.']
rows=[]
for name,guidance in variants:
    conversation_prompt.PATIENT_CNR_GUIDANCE=guidance
    for seed in args.seeds:
        bridge=Bridge(config)
        original=bridge.post_json
        def seeded(url,body,timeout):
            if url.endswith('/chat/completions'):
                body=dict(body,seed=seed)
                if args.temperature is not None and body.get('temperature'):
                    body['temperature']=args.temperature
            return original(url,body,timeout)
        bridge.post_json=seeded
        key=bridge.new_session('ivan-work-exhaustion')['session_id']
        bridge.turn(key,'',True)
        for prompt in prompts:
            r=bridge.turn(key,prompt)
            row={'variant':name,'seed':seed,'prompt':prompt,'text':' '.join(s['text'] for s in r['segments']),
                'emotions':[s['emotion'] for s in r['segments']],'generation_ms':r['generation_ms']}
            rows.append(row);args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(row,ensure_ascii=True),flush=True)
conversation_prompt.PATIENT_CNR_GUIDANCE=current
