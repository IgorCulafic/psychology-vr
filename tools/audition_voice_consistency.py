"""Controlled identity-consistency experiments; keep original auditions unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_MODULES_CACHE'] = str(ROOT / '.cache/alternative-tts/hf-modules')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
SENTENCES = ['Nisam očekivao da ćete to reći.', 'Toliko toga želim da vam kažem.', 'Dajte mi samo trenutak da saberem misli.']
LINE = ' '.join(SENTENCES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=['omnivoice', 'higgs'])
    parser.add_argument('--higgs-refine', action='store_true', help='Full-reference anger with two modest sampling changes')
    args = parser.parse_args()
    if args.higgs_refine and args.model != 'higgs':
        parser.error('--higgs-refine requires higgs')
    import numpy as np
    import soundfile as sf
    import torch
    import transformers
    torch.set_num_threads(8)
    out = ROOT / 'docs/generated/fish-local' / ('higgs-refinement' if args.higgs_refine else 'voice-consistency') / args.model
    out.mkdir(parents=True, exist_ok=True)
    refs = {}
    for name, file in [('short','clone-test-1-short'),('full','clone-test-1')]:
        path = ROOT / 'docs/generated/fish-local/references' / (file + '.wav')
        refs[name] = dict(path=path, text=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))['text'], sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report = dict(model=args.model, seed=42, torch=torch.__version__, transformers=transformers.__version__, samples=[],
                  note='Identity-preservation candidates, not verified fixes. Native listening assessment pending.')
    print('Loading '+args.model, flush=True)
    if args.model == 'omnivoice':
        from omnivoice import OmniVoice
        model = OmniVoice.from_pretrained(str(ROOT/'.cache/omnivoice'),device_map='cuda:0',dtype=torch.bfloat16)
        prompt = model.create_voice_clone_prompt(ref_audio=str(refs['short']['path']),ref_text=refs['short']['text'])
        rate = model.sampling_rate
        jobs = [
            dict(id='guidance-3',label='Higher guidance · 3 instead of 2',reference='short',text=LINE,num_step=32,guidance_scale=3.0),
            dict(id='steps-64',label='More decoding steps · 64 instead of 32',reference='short',text=LINE,num_step=64,guidance_scale=2.0),
            dict(id='sentence-reset',label='Same reference reapplied for each sentence',reference='short',text=LINE,num_step=32,guidance_scale=2.0,split=True),
        ]
        def synthesize(job):
            parts=[]; boundaries=[]; cursor=0
            for i, text in enumerate(SENTENCES if job.get('split') else [job['text']]):
                torch.manual_seed(42); torch.cuda.manual_seed_all(42)
                a=model.generate(text=text,language='sr',voice_clone_prompt=prompt,num_step=job['num_step'],
                                 guidance_scale=job['guidance_scale'],speed=1.0)[0]
                if i:
                    parts.append(np.zeros(round(.12*rate),dtype=np.float32)); cursor+=.12
                boundaries.append(dict(text=text,start_seconds=round(cursor,3),duration_seconds=round(len(a)/rate,3)))
                parts.append(a); cursor+=len(a)/rate
            job['segments']=boundaries
            return np.concatenate(parts)
    else:
        from transformers import AutoConfig,AutoTokenizer,AutoModelForCausalLM
        path=str(ROOT/'.cache/higgs-transformers')
        config=AutoConfig.from_pretrained(path,trust_remote_code=True)
        config.audio_tokenizer_id=str(ROOT/'.cache/higgs-audio-v2-tokenizer')
        tokenizer=AutoTokenizer.from_pretrained(path)
        model=AutoModelForCausalLM.from_pretrained(path,config=config,trust_remote_code=True,dtype=torch.bfloat16).to('cuda').eval()
        model.get_audio_codec()
        rate=model.config.sample_rate
        for ref in refs.values():
            a,sr=sf.read(ref['path'],dtype='float32')
            ref['codes']=model._encode_reference(torch.from_numpy(a),sr)
        jobs=[
            dict(id='full-neutral',label='Full 25-second reference · neutral',reference='full',text=LINE,temperature=.7),
            dict(id='full-angry',label='Full 25-second reference · angry',reference='full',text='<|emotion:anger|>'+LINE,temperature=.7),
            dict(id='lower-temp-angry',label='Original short reference · angry · lower temperature',reference='short',text='<|emotion:anger|>'+LINE,temperature=.45),
        ]
        if args.higgs_refine:
            jobs=[
                dict(id='full-angry-temp-060',label='Full reference · anger · temperature 0.60',reference='full',text='<|emotion:anger|>'+LINE,temperature=.6,top_p=.95),
                dict(id='full-angry-top-p-085',label='Full reference · anger · top-p 0.85',reference='full',text='<|emotion:anger|>'+LINE,temperature=.7,top_p=.85),
            ]
        def synthesize(job):
            ref=refs[job['reference']]
            return model.generate_speech(job['text'],tokenizer,reference_codes=ref['codes'],reference_text=ref['text'],
                                         temperature=job['temperature'],top_p=job.get('top_p',.95),top_k=50,max_new_tokens=700).numpy()
    for job in jobs:
        print('START '+job['id'],flush=True)
        torch.manual_seed(42); torch.cuda.manual_seed_all(42)
        torch.cuda.synchronize(); start=time.perf_counter()
        with torch.inference_mode(): a=np.asarray(synthesize(job),dtype=np.float32).reshape(-1)
        torch.cuda.synchronize()
        assert len(a)>0 and np.isfinite(a).all()
        gain=min(1.,.98/max(float(np.abs(a).max()),1e-8))
        sf.write(out/(job['id']+'.wav'),a*gain,rate,subtype='PCM_16')
        job.update(file=job['id']+'.wav',sample_rate=rate,duration_seconds=round(len(a)/rate,3),generation_seconds=round(time.perf_counter()-start,3),
                   reference_sha256=refs[job['reference']]['sha256'],reference_text=refs[job['reference']]['text'],output_gain=gain)
        report['samples'].append(job)
        (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('OK '+json.dumps(job,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
