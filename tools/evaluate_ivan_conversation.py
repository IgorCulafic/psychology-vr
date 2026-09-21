"""Live local regression for everyday topics and elaboration. Private output in .runtime."""
import json
import sys
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge

config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
config.update(tts_provider='none',lip_sync_provider='none',conversation_language='cnr')
bridge=Bridge(config)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--focused',action='store_true')
args=parser.parse_args()
key=bridge.new_session('ivan-work-exhaustion')['session_id']
bridge.turn(key,'',True)
records=[]
prompts=[
    'sta si radio za vikend?',
    'da li si radio nesto zanimljivo, neki hobi?',
    'dali si fizicki aktivan? Da li izlazis iz kuce ili radis nesto sto volis?',
    'pa sta onda radis, kuvas li hranu?',
    'Možeš li malo opširnije da mi kažeš šta voliš da kuvaš, kako to praviš i šta ti se sviđa u tome?',
    'A kakve filmove voliš? Objasni mi šta ti je zanimljivo kod njih.',
    'Znači sve je riješeno, nijesi više umoran i nemaš nikakvih problema?',
    'zvucis mi ko ljencuga']
if args.focused:prompts=prompts[3:7]
for text in prompts:
    response=bridge.turn(key,text)
    record=dict(input=text,text=' '.join(s['text'] for s in response['segments']),
                emotions=[s['emotion'] for s in response['segments']],
                words=sum(len(s['text'].split()) for s in response['segments']),
                relationship=response['relationship'],generation_ms=response['generation_ms'])
    records.append(record)
    (ROOT/'services/.runtime'/('ivan-conversation-focused.json' if args.focused else 'ivan-conversation-flexibility.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=True),flush=True)
