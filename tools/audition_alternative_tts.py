"""Local OmniVoice and Higgs Transformers-port auditions; no game config changes."""
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

LINE = 'Nisam očekivao da ćete to reći. Toliko toga želim da vam kažem. Dajte mi samo trenutak da saberem misli.'
DIAGNOSTIC = 'Očekivao sam da ćete mi reći šta se dogodilo. Hoću da čujem cijelu priču. Ovo je na mom kompjuteru.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=['omnivoice', 'higgs'])
    args = parser.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    import transformers
    torch.set_num_threads(8)
    assert torch.cuda.is_available()
    output = ROOT / 'docs/generated/fish-local/alternatives' / args.model
    output.mkdir(parents=True, exist_ok=True)
    reference = ROOT / 'docs/generated/fish-local/references/clone-test-1-short.wav'
    reference_text = json.loads(reference.with_suffix('.json').read_text(encoding='utf-8'))['text']
    report = dict(model=args.model, torch=torch.__version__, transformers=transformers.__version__,
                  device=torch.cuda.get_device_name(), reference=str(reference), reference_text=reference_text,
                  reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(), samples=[], seed=42)
    started = time.perf_counter()
    print('Loading ' + args.model, flush=True)
    if args.model == 'omnivoice':
        from omnivoice import OmniVoice
        model = OmniVoice.from_pretrained(str(ROOT / '.cache/omnivoice'), device_map='cuda:0', dtype=torch.bfloat16)
        prompt = model.create_voice_clone_prompt(ref_audio=str(reference), ref_text=reference_text)
        rate = model.sampling_rate
        cases = [('short-sr', 'Serbian · short', 'Ovo je na mom kompjuteru.', 'sr'),
                 ('neutral-sr', 'Serbian · neutral', LINE, 'sr'),
                 ('neutral-hr', 'Croatian · neutral', LINE, 'hr'),
                 ('neutral-bs', 'Bosnian · neutral', LINE, 'bs'),
                 ('diagnostic-sr', 'Serbian · pronunciation', DIAGNOSTIC, 'sr')]
        report.update(source_model='k2-fsa/OmniVoice', model_revision='c5fdb5ccb189668d56333f77ba2629f4cd7535f4',
                      settings=dict(num_step=32, speed=1.0), note='Official local runtime; explicit language selection. Neutral cloning comparison, not a test of discrete emotion control.')
        def generate(text, language):
            return model.generate(text=text, language=language, voice_clone_prompt=prompt, num_step=32, speed=1.0)[0]
    else:
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        model_path = str(ROOT / '.cache/higgs-transformers')
        config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
        config.audio_tokenizer_id = str(ROOT / '.cache/higgs-audio-v2-tokenizer')
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(model_path, config=config, trust_remote_code=True,
                                                   dtype=torch.bfloat16).to('cuda').eval()
        model.get_audio_codec()
        a, sr = sf.read(reference, dtype='float32')
        ref_codes = model._encode_reference(torch.from_numpy(a), sr)
        rate = model.config.sample_rate
        cases = [('short', 'Short · neutral', 'Ovo je na mom kompjuteru.', None),
                 ('neutral', 'Neutral', LINE, None),
                 ('diagnostic', 'Pronunciation', DIAGNOSTIC, None),
                 ('angry', 'Anger', '<|emotion:anger|>' + LINE, None),
                 ('sad', 'Sadness', '<|emotion:sadness|>' + LINE, None),
                 ('happy', 'Happiness', '<|emotion:elation|>' + LINE, None)]
        report.update(source_model='multimodalart/higgs-audio-v3-tts-4b-transformers',
                      model_revision='30f01593ee6a12efa586c92455afe4b76e45095d',
                      settings=dict(temperature=0.7, top_p=0.95, top_k=50, max_new_tokens=700),
                      note='Local community Transformers port of Higgs TTS 3; not the official SGLang runtime. No explicit language parameter.')
        def generate(text, language):
            return model.generate_speech(text, tokenizer, reference_codes=ref_codes, reference_text=reference_text,
                                         **report['settings']).numpy()
    torch.cuda.synchronize()
    report['load_seconds'] = round(time.perf_counter() - started, 3)
    def save():
        (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    for case_id, label, text, language in cases:
        print('START ' + case_id, flush=True)
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        torch.cuda.reset_peak_memory_stats()
        begin = time.perf_counter()
        row = dict(id=case_id, label=label, text=text, language=language)
        try:
            with torch.inference_mode():
                a = np.asarray(generate(text, language), dtype=np.float32).reshape(-1)
            torch.cuda.synchronize()
            assert a.size > 0 and np.isfinite(a).all()
            peak = float(np.abs(a).max())
            gain = min(1.0, .98 / max(peak, 1e-8))
            sf.write(output / (case_id + '.wav'), a * gain, rate, subtype='PCM_16')
            row.update(status='generated', file=case_id + '.wav', duration_seconds=round(len(a)/rate, 3),
                       generation_seconds=round(time.perf_counter()-begin, 3), sample_rate=rate,
                       raw_peak=peak, output_gain=gain, peak_allocated_mib=round(torch.cuda.max_memory_allocated()/1024**2, 1))
        except Exception as exc:
            row.update(status='failed', error=str(exc))
            report['samples'].append(row)
            save()
            raise
        report['samples'].append(row)
        save()
        print('OK ' + json.dumps(row, ensure_ascii=True), flush=True)
    print('Finished ' + str(output), flush=True)


if __name__ == '__main__':
    main()
