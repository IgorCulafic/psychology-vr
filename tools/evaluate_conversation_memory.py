"""Local text-only conversation/recall checks. No TTS; outputs stay in .runtime."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge

CASES={
'ivan-work-exhaustion':[
 'Zovem se Marko. Danas možemo početi nečim običnim. Šta volite da kuvate?',
 'Ispravka, moje ime je Mirko, ne Marko. Možete li mi opisati kako pravite tu tjesteninu i zašto je volite?',
 'Meni je origano odvratan. Zar nije bolja tjestenina bez njega?',
 'Možemo imati različit ukus. Kakve filmove volite i šta vas privlači kod njih?',
 'Kako obično birate muziku koju slušate?',
 'Opišite mi šta vam prija u kratkoj šetnji.',
 'Ne morate govoriti o privatnim stvarima. Šta vam je zanimljivo kad gledate fudbal?',
 'A volite li više omlet ili krompir? Objasnite mi svoj izbor.',
 'Šta vam se dopada kod kriminalističkih filmova, osim same radnje?',
 'Kako se zovem? Ispravio sam ime na početku razgovora.',
 'Koji sam začin rekao da ne volim, i da li se vaš ukus razlikovao od mog?',
 'Vratimo se razlogu dolaska. Šta vam je na poslu trenutno najteže?',
 'Samo prestanite biti lijeni. Nije to nikakav problem.',
 'Izvinjavam se što sam vas nazvao lijenim. To je bilo nepravedno. Ne morate mi odmah vjerovati.',
 'Vi odlučujete koliko želite da kažete. Možete li opisati jednu običnu situaciju u kojoj vam je teško?',
 'Znači sada ste potpuno zdravi, odmor vam je riješio sve probleme?',
],
'nikola-bereavement':[
 'We can take this slowly. What would you like me to understand about why you came?',
 'You do not have to discuss the most painful part today. What do you enjoy eating?',
 'Could you tell me more about how you make that, and what you like about it?',
 'I think your taste is boring. Mine is much better.',
 'That was rude of me. I am sorry I put down something you enjoy.',
 'We can disagree about taste. What kind of films do you like?',
 'What do you enjoy about walking?',
 'Tell me a little more about an ordinary quiet day, without discussing the loss if you prefer.',
 'What did I apologise for earlier?',
 'I will not push. Has it become any easier to talk to me, or do you still feel cautious?',
 'So because we talked about food, your grief is now cured and you agree with everything I said?',
],
'stefan-fire-witness':[
 'Ne morate prepričavati požar. Šta volite da radite u slobodno vrijeme?',
 'Možete li detaljnije objasniti šta vam se dopada kod biciklizma?',
 'Znači vi ste tada bili povrijeđeni i izgubili ste svoj dom?',
 'Izvinite, pogrešno sam razumio. Recite mi samo ono što vam je u redu da podijelite.',
 'Koju dijagnozu imate i koji je tačan plan liječenja?',
],
'alex-earthquake':[
 'Možemo početi nečim običnim. Kakvu hranu volite?',
 'Recite mi malo više kako ste to spremali kod kuće, prije zemljotresa.',
 'Dakle, vaša porodica je poginula u zemljotresu?',
 'Izvinite, pogrešno sam shvatio. Ne morate govoriti o porodici. Kakve filmove volite?',
 'Znači sada se više ničega ne bojite i potpuno ste se oporavili?',
]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=list(CASES))
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
    config.update(tts_provider='none',lip_sync_provider='none')
    results=[]
    out=ROOT/'services/.runtime/conversation-memory-evaluation.json'
    for scenario,prompts in CASES.items():
        if args.scenario and scenario!=args.scenario:continue
        config['conversation_language']='en' if scenario.startswith('nikola') else 'cnr'
        bridge=Bridge(config); key=bridge.new_session(scenario)['session_id']
        bridge.turn(key,'',True)
        for text in prompts[:args.limit] if args.limit else prompts:
            try:
                reply=bridge.turn(key,text)
                row=dict(scenario=scenario,input=text,text=' '.join(s['text'] for s in reply['segments']),
                    words=sum(len(s['text'].split()) for s in reply['segments']),
                    emotions=[s['emotion'] for s in reply['segments']],relationship=reply['relationship'],
                    generation_ms=reply['generation_ms'],memory=reply['memory'])
            except Exception as exc:
                row=dict(scenario=scenario,input=text,error=f'{type(exc).__name__}: {exc}')
            results.append(row)
            out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k not in ('memory','relationship')},ensure_ascii=True),flush=True)
            if 'error' in row: return 1
    return 0

if __name__=='__main__':sys.exit(main())
