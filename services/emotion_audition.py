"""Play local Higgs fixtures through the existing Unity conversation protocol.

This is a controlled audition, not live dialogue or live speech synthesis.
"""
import argparse
import array
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import wave
from http.server import ThreadingHTTPServer

from alex_service import Bridge, ContractError, ROOT, make_handler, validate_reply, validate_mouth_cues


class AuditionBridge(Bridge):
    def __init__(self, config, manifest, prepare=True):
        config = dict(config, dialogue_provider='controlled-audition', tts_provider='higgs-recorded')
        super().__init__(config)
        self.cases = {}
        self.by_segment = {}
        self.prepared = {}
        for entry in manifest['cases']:
            case = dict(entry)
            key = case['id']
            if key in self.cases:
                raise ContractError('Duplicate audition ID')
            segment = validate_reply({'segments': [case['segment']]})[0]
            path = (ROOT / case['audio']).resolve()
            if not path.is_relative_to(ROOT.resolve()):
                raise ContractError('Audition audio must stay inside the project')
            with wave.open(str(path)) as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    raise ContractError('Audition audio must be mono PCM16')
                duration = wav.getnframes() / wav.getframerate()
                if not .2 <= duration <= 45:
                    raise ContractError('Audition audio must be 0.2–45 seconds')
            signature = self.signature(segment)
            if signature in self.by_segment:
                raise ContractError('Audition segments must identify unique clips')
            case.update(segment=segment, path=path, duration=duration)
            self.cases[key] = case
            self.by_segment[signature] = case
            if prepare:
                self.prepared[signature] = self.prepare_alignment(case)
        if not 1 <= len(self.cases) <= 4:
            raise ContractError('Expected one to four audition cases')

    @staticmethod
    def signature(segment):
        return segment['text'], segment['emotion'], segment['voice_style']

    def prepare_alignment(self, case):
        executable = ROOT / self.config['rhubarb_path']
        digest = hashlib.sha256(case['path'].read_bytes()).hexdigest()
        cache = self.runtime / ('audition-phonetic-' + digest + '.json')
        try:
            if cache.is_file():
                raw = json.loads(cache.read_text(encoding='utf-8'))
            else:
                result = subprocess.run([str(executable), '-r', 'phonetic', '-f', 'json',
                                         '--extendedShapes', 'X', '--threads', '2', str(case['path'])],
                                        check=True, capture_output=True, text=True, timeout=30,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                raw = json.loads(result.stdout)
                cache.write_text(json.dumps(raw), encoding='utf-8')
            return validate_mouth_cues(raw['mouthCues'], case['duration']), 'rhubarb_phonetic'
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            print('Audition alignment fallback: ' + type(exc).__name__, flush=True)
            return [], 'audio_envelope'

    def generate(self, text, history, opening, state, profile):
        # No requests reach the LLM. Unknown commands cannot produce mismatched speech.
        words = set(re.findall(r'[^\W\d_]+', text.casefold()))
        if opening or words & {'neutral', 'neutralno', 'neutralan', 'neutralni', 'неутрално', 'неутралан'}:
            keys = ['neutral']
        elif words & {'compare', 'comparison', 'uporedi', 'uporedite', 'usporedi', 'упореди', 'упоредите'}:
            keys = list(self.cases)
        elif words & {'closer', 'close', 'blaže', 'blaze', 'blaži', 'blazi', 'блаже', 'блажи'}:
            keys = ['closer']
        elif words & {'angry', 'anger', 'ljutito', 'ljut', 'ljutnja', 'ljuti', 'љутито', 'љут', 'љутња'}:
            keys = ['angry']
        else:
            print('AUDITION_UNRECOGNIZED ' + json.dumps(text[:200]), flush=True)
            raise ContractError('Voice test: say neutralno, ljutito, blaze, or uporedi (neutral, angry, closer, compare).')
        if any(key not in self.cases for key in keys):
            raise ContractError('That audition clip is unavailable')
        print('AUDITION_PLAY ' + ','.join(keys), flush=True)
        return [dict(self.cases[key]['segment']) for key in keys]

    def synthesize(self, segment, audio_id):
        case = self.by_segment[self.signature(segment)]
        path = self.runtime / (audio_id + '.wav')
        shutil.copyfile(case['path'], path)
        return '/audio/' + path.name

    def transcribe(self, encoded):
        result = super().transcribe(encoded)
        with wave.open(io.BytesIO(base64.b64decode(encoded)), 'rb') as wav:
            seconds = wav.getnframes() / wav.getframerate()
            samples = array.array('h', wav.readframes(wav.getnframes()))
        peak = max((abs(sample) for sample in samples), default=0) / 32768
        # Local audition log only; raw microphone recordings are not saved.
        print('AUDITION_INPUT ' + json.dumps({'seconds': round(seconds, 2),
                                              'peak': round(peak, 5), 'text': result['text']}), flush=True)
        return result

    def align_mouth(self, audio_id, text):
        # Identify the exact copied clip; the neutral and angry passages share text.
        path = self.runtime / (audio_id + '.wav')
        digest = hashlib.sha256(path.read_bytes()).digest()
        for signature, case in self.by_segment.items():
            if digest == hashlib.sha256(case['path'].read_bytes()).digest():
                return self.prepared.get(signature, ([], 'audio_envelope'))
        return [], 'audio_envelope'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'services/config.local.json'))
    parser.add_argument('--manifest', default=str(ROOT / 'experiments/tts/vr-audition.json'))
    parser.add_argument('--port', type=int)
    parser.add_argument('--check', action='store_true', help='Validate clips and prepare lip sync without serving')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if config['host'] not in ('127.0.0.1', 'localhost'):
        parser.error('Auditions bind only to loopback')
    if args.port:
        config['port'] = args.port
    bridge = AuditionBridge(config, json.loads(Path(args.manifest).read_text(encoding='utf-8')))
    for key, case in bridge.cases.items():
        cues, source = bridge.prepared[bridge.signature(case['segment'])]
        print(f'AUDITION_READY {key}: {case["duration"]:.2f}s, {len(cues)} cues, {source}', flush=True)
    if args.check:
        return
    server = ThreadingHTTPServer((config['host'], config['port']), make_handler(bridge))
    print(f'Controlled Higgs audition: http://{config["host"]}:{config["port"]}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
