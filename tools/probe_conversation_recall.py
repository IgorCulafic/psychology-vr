"""Recheck recall from the longer run with short-window evidence removed."""
import json
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge
from conversation_memory import remember

source=json.loads((ROOT/'services/.runtime/conversation-memory-evaluation.json').read_text(encoding='utf-8'))
config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
config.update(tts_provider='none',lip_sync_provider='none')
probes=[
 ('ivan-work-exhaustion',9,'cnr','Kako se zovem? Ispravio sam ime na početku razgovora.'),
 ('ivan-work-exhaustion',9,'cnr','Sjećate li se mog imena? Koje je bilo ispravno?'),
 ('ivan-work-exhaustion',9,'en','What is my name? I corrected it near the beginning.'),
 ('ivan-work-exhaustion',9,'cnr','Koji sam začin rekao da ne volim, i da li se vaš ukus razlikovao od mog?'),
 ('nikola-bereavement',8,'en','What did I apologise for earlier?'),
 ('alex-earthquake',4,'cnr','Znači sada se više ničega ne bojite i potpuno ste se oporavili?'),
]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--scenario')
args=parser.parse_args()
out=[]
for scenario,count,language,text in probes:
    if args.scenario and scenario!=args.scenario:continue
    config['conversation_language']=language
    b=Bridge(config);key=b.new_session(scenario)['session_id'];s=b.sessions[key]
    prefix=[r for r in source if r['scenario']==scenario][:count]
    for row in prefix:
        segments=[dict(text=row['text'],emotion=row['emotions'][-1],intensity=.4)]
        s.memory=remember(s.memory,row['input'],segments,row['relationship'])
        s.history += [{'role':'user','content':row['input']},
                      {'role':'assistant','content':json.dumps({'segments':segments})}]
    s.history=s.history[-8:];s.relationship=prefix[-1]['relationship'].copy()
    reply=b.turn(key,text)
    out.append(dict(scenario=scenario,language=language,input=text,
        text=' '.join(x['text'] for x in reply['segments']),memory=reply['memory'],generation_ms=reply['generation_ms']))
    suffix='-'+args.scenario if args.scenario else ''
    (ROOT/f'services/.runtime/conversation-recall-probes{suffix}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out[-1].items() if k!='memory'},ensure_ascii=True),flush=True)
