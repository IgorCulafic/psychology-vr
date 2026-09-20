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
from performance_contract import higgs_text


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
        torch.set_num_threads(8)
        self.lock = threading.Lock()
        self.config = config
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
        audio, rate = sf.read(ref, dtype='float32', always_2d=True)
        with torch.inference_mode():
            self.reference_codes = self.model._encode_reference(torch.from_numpy(audio.mean(axis=1)), rate)
        self.rate = self.model.config.sample_rate
        print(json.dumps({'event':'loaded','quantization':config.get('higgs_quantization','bf16'),
                          'allocated_mib':round(torch.cuda.memory_allocated()/1024**2)}), flush=True)

    def synthesize(self, segment):
        import numpy as np
        import soundfile as sf
        # Fail fast instead of allowing timed-out clients to queue hours of GPU work.
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError('Speech worker is busy; retry when the current reply finishes')
        try:
            torch = self.torch
            start = time.perf_counter()
            torch.manual_seed(42)
            torch.cuda.manual_seed_all(42)
            with torch.inference_mode():
                audio = self.model.generate_speech(higgs_text(segment), self.tokenizer,
                    reference_codes=self.reference_codes, reference_text=self.reference_text,
                    temperature=self.config.get('higgs_temperature', .7), top_p=.95, top_k=50,
                    max_new_tokens=900).numpy()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not audio.size or not np.isfinite(audio).all() or len(audio)/self.rate > 35:
                raise ValueError('Speech generation returned invalid or overlong audio')
            audio *= min(1., .98 / max(float(np.abs(audio).max()), 1e-8))
            output = io.BytesIO()
            sf.write(output, audio, self.rate, format='WAV', subtype='PCM_16')
            elapsed = round(time.perf_counter() - start, 3)
            print(json.dumps({'event':'speech', 'emotion':segment['emotion'],
                'characters':len(segment['text']), 'audio_seconds':round(len(audio)/self.rate,3),
                'generation_seconds':elapsed}), flush=True)
            return output.getvalue()
        finally:
            self.lock.release()


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
                self.respond(200, {'ok':True, 'provider':'higgs', 'busy':voice.lock.locked(),
                    'quantization':getattr(voice,'config',{}).get('higgs_quantization','bf16')})
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
                if not isinstance(body, dict) or set(body) != {'segment'}:
                    raise ContractError('Expected segment only')
                segment = validate_reply({'segments':[body['segment']]})[0]
                self.respond(200, voice.synthesize(segment), 'audio/wav')
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
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(voice))
    print('HIGGS_READY port='+str(args.port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
