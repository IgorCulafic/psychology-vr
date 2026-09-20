"""Local Unity bridge. Core and scripted/Windows-voice mode use only the stdlib.

Run: python services/alex_service.py --config services/config.example.json
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import math
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from performance_contract import GAZES, TIMING_DEFAULTS, TIMING_LIMITS, FIELDS, directions, PERFORMANCE_PROMPT

ROOT = Path(__file__).resolve().parents[1]
EMOTION_CATALOG = json.loads((ROOT/'unity/Assets/PsychologyVR/Resources/EmotionCatalog.json').read_text(encoding='utf-8'))
EMOTIONS = tuple(e['name'] for e in EMOTION_CATALOG['emotions'])
EMOTION_ALIASES = {a['name']:a['emotion'] for a in EMOTION_CATALOG['aliases']}
GESTURES = ('none', 'look_down', 'glance_away', 'nod', 'hand_fidget', 'wince', 'wipe_tear')
VOICES = ('normal', 'subdued', 'hesitant', 'tense', 'gentle')
SEGMENT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['segments'],
    'properties': {'segments': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': list(FIELDS),
        'properties': {
            'text': {'type': 'string'},
            'emotion': {'type': 'string', 'enum': list(EMOTIONS)},
            'intensity': {'type': 'number'},
            'gesture': {'type': 'string', 'enum': list(GESTURES)},
            'voice_style': {'type': 'string', 'enum': list(VOICES)},
            'gaze': {'type': 'string', 'enum': list(GAZES)},
            **{name: {'type': 'number', 'minimum': low, 'maximum': high}
               for name, (low, high) in TIMING_LIMITS.items()},
        }}}},
}

class ContractError(ValueError):
    pass

class StaleTurn(Exception):
    pass

def validate_mouth_cues(value, duration):
    """Accept bounded, ordered timings from the local aligner, never from the LLM."""
    if not isinstance(value,list) or len(value)>4000:raise ValueError('Invalid mouth cues')
    result=[]; previous=0.0
    for cue in value:
        if not isinstance(cue,dict):raise ValueError('Invalid mouth cue')
        start,end=cue.get('start'),cue.get('end')
        if any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) for t in (start,end)):
            raise ValueError('Invalid mouth timing')
        if start<previous-.001 or start<0 or start>=duration or end<=start or end>duration+.1 or not isinstance(cue.get('value'),str) or cue['value'] not in ('A','B','C','D','E','F','X'):
            raise ValueError('Invalid mouth interval')
        result.append({'start':start,'end':min(end,duration),'value':cue['value']});previous=end
    return result

def validate_reply(content: str | dict) -> list[dict]:
    """Never use unparsed model output as speech, even on failure."""
    if isinstance(content, str):
        # Some backends return complete reasoning blocks in content rather than a field.
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.S | re.I).strip()
        if '<think' in content.lower() or '</think' in content.lower():
            raise ContractError('Incomplete reasoning block')
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content).strip()
        try:
            content = json.loads(content)
        except (ValueError, TypeError) as exc:
            raise ContractError('Model response was not valid JSON') from exc
    if not isinstance(content, dict) or set(content) != {'segments'}:
        raise ContractError('Expected only a segments object')
    segments = content['segments']
    if not isinstance(segments, list) or not 1 <= len(segments) <= 4:
        raise ContractError('Expected one to four speech segments')
    result = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ContractError('Invalid segment')
        text = segment.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 700:
            raise ContractError('Speech must be 1–700 characters')
        # Fail closed on control syntax inside speech; do not guess what was intended.
        if re.search(r'[<>\[\]{}*`]|\btrigger\s*:', text, re.I):
            raise ContractError('Control or stage-direction syntax inside speech')
        intensity = segment.get('intensity', .3)
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not math.isfinite(intensity):
            raise ContractError('Intensity must be a finite number')
        emotion=segment.get('emotion')
        if isinstance(emotion,str):emotion=EMOTION_ALIASES.get(emotion,emotion)
        try:
            performance = directions(segment)
        except ValueError as exc:
            raise ContractError(str(exc)) from exc
        result.append({
            **performance,
            'text': text.strip(),
            'emotion': emotion if emotion in EMOTIONS else 'neutral',
            'intensity': min(1., max(0., intensity)),
            'gesture': segment.get('gesture') if segment.get('gesture') in GESTURES else 'none',
            'voice_style': segment.get('voice_style') if segment.get('voice_style') in VOICES else 'normal',
        })
    return result

@dataclass
class Session:
    scenario_id: str = 'alex-earthquake'
    profile: dict = field(default_factory=dict)
    generation: int = 0
    history: list[dict] = field(default_factory=list)
    busy: bool = False
    emotion: str = 'anxious'
    intensity: float = .65

class Bridge:
    def __init__(self, config: dict):
        self.config = config
        self.catalog = json.loads((ROOT / 'characters/catalog.json').read_text(encoding='utf-8'))
        self.profiles = {}
        for entry in self.catalog['scenarios']:
            profile_path = (ROOT / 'characters' / entry['profile']).resolve()
            if not profile_path.is_relative_to((ROOT / 'characters').resolve()):
                raise ContractError('Profile path must stay inside characters')
            if entry['id'] in self.profiles:
                raise ContractError('Duplicate scenario ID')
            self.profiles[entry['id']] = json.loads(profile_path.read_text(encoding='utf-8'))
        if self.catalog['default_scenario_id'] not in self.profiles:
            raise ContractError('Default scenario is missing')
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()
        self.speech_lock = threading.Lock()
        self.inference_lock = threading.Lock()
        self.stt_lock = threading.Lock()
        self.stt = None
        self.kokoro = None
        self.runtime = ROOT / 'services/.runtime'
        self.runtime.mkdir(parents=True, exist_ok=True)

    def public_catalog(self):
        return {'default_scenario_id': self.catalog['default_scenario_id'], 'scenarios': [
            {k: v for k, v in entry.items() if k != 'profile'} for entry in self.catalog['scenarios']]}

    def new_session(self, scenario_id=None, replace_session_id=None):
        scenario_id = scenario_id or self.catalog['default_scenario_id']
        if not isinstance(scenario_id, str) or scenario_id not in self.profiles:
            raise ContractError('Unknown scenario')
        profile = self.profiles[scenario_id]
        initial = profile.get('initial_state', {'emotion': 'neutral', 'intensity': .5})
        with self.lock:
            if replace_session_id:
                old = self.sessions[replace_session_id]
                # Retire the old ID as well as its generation: even an old request
                # arriving after this switch cannot act on the new conversation.
                old.generation += 1
                del self.sessions[replace_session_id]
            elif len(self.sessions) >= 32:
                raise ContractError('Session limit reached; restart the local bridge')
            key = uuid.uuid4().hex
            self.sessions[key] = Session(scenario_id=scenario_id, profile=profile,
                emotion=initial['emotion'], intensity=initial['intensity'])
        return {'session_id': key, 'scenario_id': scenario_id, 'character_name': profile['name'],
                'initial_emotion': initial['emotion'], 'initial_intensity': initial['intensity']}

    def invalidate(self, key, reset=False):
        with self.lock:
            session = self.sessions[key]
            session.generation += 1
            session.busy = False
            if reset:
                session.history.clear()
                initial = session.profile.get('initial_state', {'emotion': 'neutral', 'intensity': .5})
                session.emotion, session.intensity = initial['emotion'], initial['intensity']
        return {'ok': True}

    def assert_current(self, key, generation):
        with self.lock:
            if key not in self.sessions or self.sessions[key].generation != generation:
                raise StaleTurn('Turn was interrupted or reset')

    def generate(self, text, history, opening, state, profile):
        if opening:
            initial = profile.get('initial_state', {'emotion': 'neutral', 'intensity': .5})
            opening_text = profile.get('openings', {}).get(self.config.get('conversation_language'), profile['opening'])
            return [{'text': opening_text, **initial, 'gesture': 'none', 'voice_style': 'normal'}]
        if self.config['dialogue_provider'] == 'scripted':
            # A clearly labelled transport/animation demo; this does not pretend to be AI.
            examples = [
                ('I know my family is safe. I still keep expecting the floor to move.', 'anxious', 'glance_away', 'hesitant'),
                ('Losing our home has been hard. I miss having somewhere that feels like ours.', 'sad', 'look_down', 'subdued'),
                ('Could we slow down a little? My back is hurting and I need a moment.', 'frustrated', 'wince', 'tense'),
                ('It helps having someone sit here with me. I can try taking a slower breath.', 'relieved', 'nod', 'gentle'),
            ]
            if profile['name'] != 'Alex':
                return [{'text': profile['opening'], **profile.get('initial_state', {'emotion': 'neutral', 'intensity': .5}),
                         'gesture': 'none', 'voice_style': 'normal'}]
            line, emotion, gesture, voice = examples[(len(history) // 2) % len(examples)]
            return [{'text': line, 'emotion': emotion, 'intensity': .5, 'gesture': gesture, 'voice_style': voice}]
        system = json.dumps(profile, ensure_ascii=False)
        system += '\nReturn only a JSON object with a segments array. Every segment has text, emotion, intensity (0-1), gesture, voice_style, gaze, transition_seconds, pause_before_seconds, hold_after_seconds, gesture_at and gesture_duration_seconds.'
        system += '\nAllowed gestures: '+', '.join(GESTURES)+'; voices: '+', '.join(VOICES)+'; gaze: '+', '.join(GAZES)+'.'
        system += '\nCurrent simulated delivery state: ' + json.dumps(state)
        system += PERFORMANCE_PROMPT
        if self.config.get('conversation_language') == 'cnr':
            system += '\nSpeak Montenegrin, Latin script, natural ijekavian (vrijeme, osjećam, nijesam where natural). Preserve č, ć, š, ž, đ. Do not translate to English or explain the language. Avoid forced dialect and phonetic spelling. Reply directly to what the counsellor said.'
        else:
            system += '\nUse the language spoken by the counsellor. Keep replies conversational and concise.'
        system += '\nAvailable delivery states: ' + json.dumps({e['name']:e['description'] for e in EMOTION_CATALOG['emotions']})
        body = {
            'model': self.config['llm_model'],
            'messages': [{'role': 'system', 'content': system}] + history[-8:] + [{'role': 'user', 'content': text}],
            'stream': False, 'temperature': .7, 'top_p': .8, 'top_k': 20, 'max_tokens': 850,
            'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'alex_reply', 'strict': True, 'schema': SEGMENT_SCHEMA}},
        }
        data = self.post_json(self.config['llm_url'], body, self.config['llm_timeout_seconds'])
        message = data['choices'][0]['message']
        return validate_reply(message.get('content', ''))

    @staticmethod
    def post_json(url, body, timeout):
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def synthesize(self, segment, audio_id):
        path = self.runtime / (audio_id + '.wav')
        provider = self.config['tts_provider']
        if provider == 'none':
            return None
        if provider == 'windows':
            text_path = self.runtime / (audio_id + '.txt')
            text_path.write_text(segment['text'], encoding='utf-8')
            try:
                subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                    str(ROOT / 'services/synthesize.ps1'), '-TextPath', str(text_path), '-OutputPath', str(path)],
                    check=True, timeout=40, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            finally:
                text_path.unlink(missing_ok=True)
        elif provider == 'kokoro':
            from kokoro_onnx import Kokoro
            import soundfile
            if self.kokoro is None:
                self.kokoro = Kokoro(str(ROOT / '.cache/kokoro/kokoro-v1.0.onnx'), str(ROOT / '.cache/kokoro/voices-v1.0.bin'))
            # Kokoro has no arbitrary emotion-style control. Use a stable voice;
            # facial/body delivery remains independent until expressive TTS is added.
            audio, rate = self.kokoro.create(segment['text'], voice=self.config['tts_voice'], speed=.95, lang='en-us')
            soundfile.write(path, audio, rate, subtype='PCM_16')
        elif provider == 'higgs':
            request = urllib.request.Request(self.config.get('higgs_url', 'http://127.0.0.1:8766/synthesize'),
                data=json.dumps({'segment': {k: segment[k] for k in FIELDS}}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=self.config.get('tts_timeout_seconds', 120)) as response:
                data = response.read(5_000_001)
            if len(data) > 5_000_000:
                raise ContractError('Speech response exceeded limit')
            with wave.open(io.BytesIO(data)) as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or not .1 <= wav.getnframes()/wav.getframerate() <= 45:
                    raise ContractError('Invalid Higgs audio')
            path.write_bytes(data)
        elif provider == 'api':
            body = {'model': self.config['tts_model'], 'input': segment['text'],
                    'voice': self.config['tts_voice'], 'response_format': 'wav'}
            request = urllib.request.Request(self.config['tts_url'], data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
        else:
            raise ContractError('Unsupported speech provider')
        return '/audio/' + path.name

    def align_mouth(self,audio_id,text):
        if self.config.get('lip_sync_provider')!='rhubarb':return [],'audio_envelope'
        executable=ROOT/self.config.get('rhubarb_path','.tools/rhubarb/Rhubarb-Lip-Sync-1.14.0-Windows/rhubarb.exe')
        path=self.runtime/(audio_id+'.wav');dialogue=self.runtime/(audio_id+'-alignment.txt')
        try:
            with wave.open(str(path)) as wav:duration=wav.getnframes()/wav.getframerate()
            dialogue.write_text(text,encoding='utf-8')
            recognizer = ['-r','phonetic'] if self.config.get('conversation_language') == 'cnr' else ['--dialogFile',str(dialogue)]
            process=subprocess.run([str(executable),'-f','json','--extendedShapes','X','--threads','2',
                *recognizer,str(path)],capture_output=True,text=True,encoding='utf-8',
                check=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return validate_mouth_cues(json.loads(process.stdout)['mouthCues'],duration),'rhubarb'
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,wave.Error) as exc:
            print('Lip alignment unavailable; using audio envelope: '+type(exc).__name__,flush=True)
            return [],'audio_envelope'
        finally:dialogue.unlink(missing_ok=True)

    def turn(self, key, text, opening=False):
        if not isinstance(text, str) or len(text) > 2000 or (not opening and not text.strip()):
            raise ContractError('Enter 1–2000 characters')
        with self.lock:
            session = self.sessions[key]
            if session.busy:
                raise ContractError('A reply is already in progress')
            session.busy = True
            generation = session.generation
            history = list(session.history)
            state = {'emotion': session.emotion, 'intensity': session.intensity}
            profile = session.profile
        started = time.perf_counter()
        created_files = []
        committed = False
        try:
            # A cancelled request can finish remotely, but cannot publish audio/history.
            with self.inference_lock:
                self.assert_current(key, generation)
                segments = validate_reply({'segments': self.generate(text.strip(), history, opening, state, profile)})
            self.assert_current(key, generation)
            generation_ms = round((time.perf_counter() - started) * 1000)
            turn_id = uuid.uuid4().hex
            speech_ms = alignment_ms = 0
            with self.speech_lock:
                for i, segment in enumerate(segments):
                    self.assert_current(key, generation)
                    audio_id = uuid.uuid4().hex
                    created_files.append(self.runtime / (audio_id + '.wav'))
                    segment['segment_id'] = f'{turn_id}-{i}'
                    stage_started = time.perf_counter()
                    segment['audio_url'] = self.synthesize(segment, audio_id)
                    speech_ms += round((time.perf_counter() - stage_started) * 1000)
                    if segment['audio_url']:
                        self.assert_current(key,generation)
                        stage_started = time.perf_counter()
                        segment['mouth_cues'],segment['lip_sync_source']=self.align_mouth(audio_id,segment['text'])
                        alignment_ms += round((time.perf_counter() - stage_started) * 1000)
            self.assert_current(key, generation)
            with self.lock:
                self.assert_current(key, generation)
                session.history += [{'role': 'user', 'content': '[Start the session]' if opening else text.strip()},
                                    {'role': 'assistant', 'content': json.dumps({'segments': [
                                        {k: s[k] for k in FIELDS} for s in segments]})}]
                session.history = session.history[-12:]
                session.emotion, session.intensity = segments[-1]['emotion'], segments[-1]['intensity']
                committed = True
            return {'turn_id': turn_id, 'session_id': key, 'segments': segments,
                    'generation_ms': generation_ms, 'speech_ms': speech_ms, 'alignment_ms': alignment_ms,
                    'total_ms': round((time.perf_counter() - started) * 1000),
                    'dialogue_provider': self.config['dialogue_provider'], 'tts_provider': self.config['tts_provider']}
        finally:
            if not committed:
                for path in created_files:
                    path.unlink(missing_ok=True)
            with self.lock:
                if session.generation == generation:
                    session.busy = False

    def transcribe(self, encoded):
        if self.config['stt_provider'] != 'faster-whisper':
            raise ContractError('STT is disabled. Enable faster-whisper in the configuration.')
        try:
            raw = base64.b64decode(encoded, validate=True)
            with wave.open(io.BytesIO(raw)) as recording:
                if recording.getnchannels() != 1 or recording.getsampwidth() != 2:
                    raise ContractError('Expected mono PCM16 WAV')
                seconds = recording.getnframes() / recording.getframerate()
                if not .2 <= seconds <= 45:
                    raise ContractError('Recording must be 0.2–45 seconds')
        except (ValueError, wave.Error, EOFError) as exc:
            raise ContractError('Invalid WAV recording') from exc
        with self.stt_lock:
            if self.stt is None:
                from faster_whisper import WhisperModel
                model_path = ROOT / self.config['stt_model']
                model_name = str(model_path) if model_path.is_dir() else self.config['stt_model']
                self.stt = WhisperModel(model_name, device=self.config['stt_device'],
                    compute_type='int8', cpu_threads=self.config.get('stt_cpu_threads', 8),
                    download_root=str(ROOT / '.cache/whisper'))
            language = self.config.get('stt_language', 'en')
            language = None if language == 'auto' else language
            if language and language != 'en' and not self.stt.model.is_multilingual:
                raise ContractError('This STT language requires a multilingual model; replace small.en with small.')
            segments, _ = self.stt.transcribe(io.BytesIO(raw), language=language,
                                             task='transcribe', vad_filter=True)
            return {'text': ' '.join(s.text.strip() for s in segments).strip()}

def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, value):
            data = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            if self.path == '/catalog':
                self.send_json(200, bridge.public_catalog())
            elif self.path == '/health':
                self.send_json(200, {'ok': True, 'character': 'Alex', 'dialogue_provider': bridge.config['dialogue_provider'],
                    'tts_provider': bridge.config['tts_provider'], 'stt_provider': bridge.config['stt_provider'],
                    'stt_model': bridge.config.get('stt_model'),
                    'stt_language': bridge.config.get('stt_language', 'en')})
            elif re.fullmatch(r'/audio/[a-f0-9]{32}\.wav', self.path):
                path = bridge.runtime / self.path.rsplit('/', 1)[1]
                if not path.is_file():
                    return self.send_json(404, {'error': 'Audio not found'})
                data = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
            else:
                self.send_json(404, {'error': 'Not found'})

        def do_POST(self):
            # Browser pages must not be able to submit requests to this local service.
            if self.headers.get('Origin'):
                return self.send_json(403, {'error': 'Browser origins are not accepted'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8_000_000:
                    return self.send_json(413, {'error': 'Invalid request size'})
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ContractError('Expected JSON object')
                if self.path == '/session':
                    value = bridge.new_session(body.get('scenario_id'), body.get('replace_session_id'))
                elif self.path == '/turn':
                    value = bridge.turn(body['session_id'], body.get('text', ''), body.get('opening') is True)
                elif self.path in ('/interrupt', '/reset'):
                    value = bridge.invalidate(body['session_id'], reset=self.path == '/reset')
                elif self.path == '/transcribe':
                    value = bridge.transcribe(body['wav_base64'])
                else:
                    return self.send_json(404, {'error': 'Not found'})
                self.send_json(200, value)
            except StaleTurn as exc:
                self.send_json(409, {'error': str(exc)})
            except (ContractError, KeyError, ValueError, TypeError) as exc:
                self.send_json(400, {'error': str(exc)})
            except Exception as exc:
                print(f'Provider failure: {type(exc).__name__}: {exc}', flush=True)
                self.send_json(502, {'error': f'Local provider failed ({type(exc).__name__}); check the service console.'})

    return Handler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / 'services/config.example.json'))
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if config['host'] not in ('127.0.0.1', 'localhost'):
        parser.error('This prototype binds only to loopback.')
    if config['dialogue_provider'] not in ('scripted', 'llama.cpp'):
        parser.error('dialogue_provider must be scripted or llama.cpp')
    bridge = Bridge(config)
    server = ThreadingHTTPServer((config['host'], config['port']), make_handler(bridge))
    print(f"Alex bridge: http://{config['host']}:{config['port']} | dialogue={config['dialogue_provider']} | voice={config['tts_provider']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
