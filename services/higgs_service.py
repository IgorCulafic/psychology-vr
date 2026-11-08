"""Resident, loopback-only Higgs speech worker in the alternative-TTS environment.

Uses the already-auditioned, pinned local Transformers port and private full reference.
The HTTP caller sends validated directions, never paths or arbitrary synthesis tags.
"""
import argparse
import io
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from alex_service import ROOT, validate_reply, ContractError
from performance_contract import higgs_text, speech_text
from speech_language import latin_script
from voice_cast import VoiceCast


class HiggsVoice:
    def __init__(self, config):
        if config.get('higgs_quantization', 'bf16') not in ('bf16', 'int8', 'nf4'):
            raise ValueError('higgs_quantization must be bf16, int8 or nf4')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['HF_MODULES_CACHE'] = str(ROOT / '.cache/alternative-tts/hf-modules')
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        import torch
        import soundfile as sf
        from transformers import AutoConfig, AutoTokenizer, AutoModelForCausalLM
        # GPU decoding consists of many small launches. Avoid a large CPU pool
        # competing with Unity/STT; this does not change precision or sampling.
        torch.set_num_threads(config.get('higgs_cpu_threads', 1))
        self.lock = threading.Lock()
        self.config = config
        self.voice_cast = VoiceCast(ROOT, config.get('higgs_sentence_streaming', False))
        from speech_reuse import SpeechReuse
        self.speech_reuse = SpeechReuse(ROOT, config, self.voice_cast)
        self.reference_cache = {}
        self.prepared_openings = {}
        self.torch = torch
        path = str(ROOT / config.get('higgs_model', '.cache/higgs-transformers'))
        ref = ROOT / config['higgs_reference']
        self.reference_text = json.loads(ref.with_suffix('.json').read_text(encoding='utf-8'))['text']
        model_config = AutoConfig.from_pretrained(path, trust_remote_code=True, local_files_only=True)
        model_config.audio_tokenizer_id = str(ROOT / '.cache/higgs-audio-v2-tokenizer')
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        load_options = {}
        if config.get('higgs_quantization') == 'int8':
            from transformers import BitsAndBytesConfig
            load_options = dict(device_map={'':'cuda:0'}, quantization_config=BitsAndBytesConfig(
                load_in_8bit=True, llm_int8_skip_modules=['audio_head','audio_embedding']))
        elif config.get('higgs_quantization') == 'nf4':
            from transformers import BitsAndBytesConfig
            load_options = dict(device_map={'':'cuda:0'}, quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16,
                llm_int8_skip_modules=['audio_head','audio_embedding']))
        self.model = AutoModelForCausalLM.from_pretrained(path, config=model_config,
            trust_remote_code=True, local_files_only=True, dtype=torch.bfloat16, **load_options)
        if not load_options:
            self.model.to('cuda')
        # Quantized loading can report the omitted tied head as missing. Restore
        # the port's explicit tie after loading so it never uses a random head.
        self.model.tie_weights()
        if self.model._tie_audio_head and self.model.audio_head.weight.data_ptr() != self.model.audio_embedding.weight.data_ptr():
            raise RuntimeError('Higgs audio head is not tied to its reference embedding')
        self.model.eval()
        self.model.get_audio_codec()
        self.decoder = None
        if config.get('higgs_fast_decode', False):
            from higgs_decode import HiggsDecoder
            self.decoder = HiggsDecoder(self.model)
        audio, rate = sf.read(ref, dtype='float32', always_2d=True)
        with torch.inference_mode():
            self.reference_codes = self.model._encode_reference(torch.from_numpy(audio.mean(axis=1)), rate)
        self.rate = self.model.config.sample_rate
        if config.get('higgs_release_unused_vram', False):
            torch.cuda.empty_cache()
        print(json.dumps({'event':'loaded','quantization':config.get('higgs_quantization','bf16'),
                          'fast_decode':bool(self.decoder),
                          'attention':getattr(self.model.model.config,'_attn_implementation',None),
                          'allocated_mib':round(torch.cuda.memory_allocated()/1024**2)}), flush=True)

    def synthesize(self, segment, scenario_id=None):
        import numpy as np
        import soundfile as sf
        from speech_audio import checked_synthesis
        # Fail fast instead of allowing timed-out clients to queue hours of GPU work.
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError('Speech worker is busy; retry when the current reply finishes')
        try:
            torch = self.torch
            start = time.perf_counter()
            opening_key = (scenario_id, segment['emotion'], segment['text'])
            prepared = getattr(self, 'prepared_openings', {}).get(opening_key)
            if prepared is not None:
                print(json.dumps({'event':'prepared_opening','scenario_id':scenario_id,
                    'emotion':segment['emotion'],'generation_seconds':0}),flush=True)
                return prepared
            recipe = self.voice_cast.resolve(scenario_id, segment) if scenario_id is not None else None
            codes, transcript = self.reference_codes, self.reference_text
            if recipe:
                if self.config.get('higgs_quantization', 'bf16') != 'bf16' and not self.config.get('higgs_allow_quantized_cast', False):
                    raise ValueError('Assigned voice packs require approved BF16 speech; explicitly enable higgs_allow_quantized_cast for a precision comparison')
                cache_key = recipe['reference_sha256']
                if cache_key not in self.reference_cache:
                    reference, rate = sf.read(ROOT / recipe['reference'], dtype='float32', always_2d=True)
                    with torch.inference_mode():
                        self.reference_cache[cache_key] = self.model._encode_reference(
                            torch.from_numpy(reference.mean(axis=1)), rate).cpu()
                codes = self.reference_cache[cache_key]
                transcript = recipe['reference_text']
            def render(part, retry):
                seed = recipe['retry_seed' if retry else 'seed'] if recipe else 43 if retry else 42
                torch.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)
                temperature = recipe['temperature'] if recipe else self.config.get('higgs_temperature', .7)
                if retry:
                    temperature = recipe['retry_temperature'] if recipe else min(temperature,.5)
                text = recipe['tag'] + speech_text(latin_script(part['text']), self.config.get('higgs_pronunciation')) if recipe else higgs_text(part,self.config.get('higgs_pronunciation'))
                with torch.inference_mode():
                    decoder = getattr(self, 'decoder', None)
                    generate = decoder.generate if decoder else self.model.generate_speech
                    result = generate(text, self.tokenizer,
                        reference_codes=codes, reference_text=transcript,
                        temperature=temperature, top_p=recipe['top_p'] if recipe else .95,
                        top_k=recipe['top_k'] if recipe else 50,
                        max_new_tokens=recipe['max_new_tokens'] if recipe else 900).numpy()
                    if decoder:
                        print(json.dumps({'event':'speech_decode', **decoder.last_metrics}),flush=True)
                    return result
            if recipe and recipe['mode']=='sentences':
                from streaming_turns import sentence_segments
                clips=[];reports=[]
                for part in sentence_segments([segment]):
                    clip,report=checked_synthesis(part,render,self.rate)
                    if clips:clips.append(np.zeros(round(recipe['sentence_gap_seconds']*self.rate),dtype='float32'))
                    clips.append(clip);reports.append(report)
                audio=np.concatenate(clips)
                validation={'regenerated':any(r['regenerated'] for r in reports),'parts':reports}
            else:
                audio, validation = checked_synthesis(segment, render, self.rate)
            if validation['regenerated']:
                print(json.dumps({'event':'speech_regenerated', **validation}), flush=True)
            audio *= min(1., .98 / max(float(np.abs(audio).max()), 1e-8))
            output = io.BytesIO()
            sf.write(output, audio, self.rate, format='WAV', subtype='PCM_16')
            elapsed = round(time.perf_counter() - start, 3)
            print(json.dumps({'event':'speech', 'emotion':segment['emotion'],
                'scenario_id':scenario_id, 'speaker':recipe['speaker'] if recipe else 'shared',
                'preset':recipe.get('source_preset') if recipe else None,
                'mode':recipe['mode'] if recipe else 'checked',
                'temperature':recipe['temperature'] if recipe else self.config.get('higgs_temperature',.7),
                'characters':len(segment['text']), 'audio_seconds':round(len(audio)/self.rate,3),
                'generation_seconds':elapsed}), flush=True)
            return output.getvalue()
        finally:
            try:
                if self.config.get('higgs_release_unused_vram', False):
                    # Return unused prefill/codec allocator blocks to the driver
                    # so dialogue/rendering can use them. Weights stay resident.
                    self.torch.cuda.empty_cache()
            finally:
                self.lock.release()

    def prepare_openings(self):
        """Warm kernels/references before play; only cache fixed character lines.

        New conversational replies are always synthesized from their actual text.
        Nothing here plays audio or creates a student session.
        """
        catalog=json.loads((ROOT/'characters/catalog.json').read_text(encoding='utf-8'))
        for scenario in catalog['scenarios']:
            if scenario['id'] not in self.voice_cast.scenarios:continue
            profile=json.loads((ROOT/'characters'/scenario['profile']).read_text(encoding='utf-8'))
            text=profile.get('openings',{}).get(self.config.get('conversation_language'),profile['opening'])
            segment=validate_reply({'segments':[dict(text=text,**profile.get('initial_state',{'emotion':'neutral','intensity':.5}))]})[0]
            for part in self.voice_cast.delivery_segments(scenario['id'],[segment]):
                try:
                    reuse=getattr(self,'speech_reuse',None)
                    cache_key=None
                    cached=None
                    if reuse and reuse.cache_enabled:
                        cache_key,cached=reuse.lookup(dict(part,scenario_id=scenario['id']))
                    if cached:
                        audio=cached['audio']
                        print(json.dumps({'event':'opening_cache_hit','scenario_id':scenario['id']}),flush=True)
                    else:
                        audio=self.synthesize(part,scenario['id'])
                        if cache_key:
                            # Bridge calculates/validates mouth cues on first playback.
                            reuse.put(cache_key,audio,[],'pending',None)
                    self.prepared_openings[(scenario['id'],part['emotion'],part['text'])]=audio
                except ValueError as exc:
                    # A rejected warm-up clip must not prevent other characters
                    # from loading. Normal synthesis can retry it on selection.
                    print(json.dumps({'event':'opening_warmup_skipped','scenario_id':scenario['id'],
                        'reason':str(exc)}),flush=True)
        print(json.dumps({'event':'openings_prepared','count':len(self.prepared_openings)}),flush=True)


def make_handler(voice):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, data, kind='application/json'):
            if not isinstance(data, bytes):
                data = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            if self.path == '/health':
                from inference_runtime import config_signature
                self.respond(200, {'ok':True, 'provider':'higgs', 'busy':voice.lock.locked(),
                    'config_signature':config_signature(voice.config),
                    'quantization':getattr(voice,'config',{}).get('higgs_quantization','bf16'),
                    'fast_decode':getattr(voice,'config',{}).get('higgs_fast_decode',False),
                    'cast_precision_comparison':getattr(voice,'config',{}).get('higgs_allow_quantized_cast',False),
                    'prepared_openings':len(getattr(voice,'prepared_openings',{}))})
            else:
                self.respond(404, {'error':'Not found'})

        def do_POST(self):
            if self.headers.get('Origin'):
                return self.respond(403, {'error':'Browser origins are not accepted'})
            if self.path != '/synthesize':
                return self.respond(404, {'error':'Not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16000:
                    return self.respond(413, {'error':'Invalid request size'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or 'segment' not in body or set(body) - {'segment','scenario_id'}:
                    raise ContractError('Expected segment and optional scenario_id')
                segment = validate_reply({'segments':[body['segment']]})[0]
                if 'scenario_id' in body:
                    scenario=body['scenario_id']
                    if not isinstance(scenario,str) or scenario not in voice.voice_cast.scenarios:
                        raise ContractError('Unknown voice scenario')
                    result=voice.synthesize(segment,scenario)
                else:result=voice.synthesize(segment)
                self.respond(200, result, 'audio/wav')
            except BlockingIOError as exc:
                self.respond(409, {'error':str(exc)})
            except (ValueError, TypeError, KeyError) as exc:
                self.respond(400, {'error':str(exc)})
            except Exception as exc:
                print('Higgs failure: '+type(exc).__name__, flush=True)
                self.respond(502, {'error':'Higgs generation failed: '+type(exc).__name__})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT/'services/config.local.json'))
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    voice = HiggsVoice(config)
    if config.get('higgs_prepare_openings',True):voice.prepare_openings()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(voice))
    print('HIGGS_READY port='+str(args.port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
