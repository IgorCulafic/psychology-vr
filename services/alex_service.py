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
import urllib.parse
import uuid
import wave
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from performance_contract import GAZES, TIMING_DEFAULTS, TIMING_LIMITS, FIELDS, directions, PERFORMANCE_PROMPT, PATIENT_PERFORMANCE_PROMPT
from conversation_prompt import character_prompt, conversation_guidance
from conversation_memory import remember, select as select_memories, memory_prompt, MAX_TURNS
from session_log import SessionLog, SessionLogError
from streaming_turns import StreamingTurns, sentence_segments
from performance_contract import refine_delivery
from speech_language import whisper_language, latin_script, obvious_english_leak
from patient_relationship import (initial_relationship, validate_appraisal, advance,
    relationship_prompt, enforce_boundary_cues, ending_segments, APPRAISAL_PROMPT, APPRAISAL_SCHEMA, wants_fuller_reply)

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
    relationship: dict | None = None
    memory: list[dict] = field(default_factory=list)
    journal: SessionLog | None = None
    stream: dict | None = None
    recent_gestures: list[str] = field(default_factory=list)

class Bridge(StreamingTurns):
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
        self.context_limit = None
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
            old = self.sessions[replace_session_id] if replace_session_id else None
            if old is None and len(self.sessions) >= 32:
                raise ContractError('Session limit reached; restart the local bridge')
            key = uuid.uuid4().hex
            journal = SessionLog(ROOT,self.config,key,scenario_id,profile['name'])
            if replace_session_id:
                if old.stream and not old.stream['closed']:
                    self.finish_stream(replace_session_id,old.stream['turn_id'],old.stream['completed_count'],old.stream['partial_seconds'],'replaced')
                old.journal.append('session_ended',reason='replaced',generation=old.generation,
                                   next_archive_id=journal.archive_id)
                # Retire the old ID as well as its generation: even an old request
                # arriving after this switch cannot act on the new conversation.
                old.generation += 1
                del self.sessions[replace_session_id]
            self.sessions[key] = Session(scenario_id=scenario_id, profile=profile,
                emotion=initial['emotion'], intensity=initial['intensity'], relationship=initial_relationship(profile),journal=journal)
        return {'session_id': key, 'scenario_id': scenario_id, 'character_name': profile['name'],
                'generation':0,
                'initial_emotion': initial['emotion'], 'initial_intensity': initial['intensity'],
                'relationship': initial_relationship(profile)}

    def invalidate(self, key, reset=False):
        with self.lock:
            session = self.sessions[key]
            if session.stream and not session.stream['closed']:
                self.finish_stream(key,session.stream['turn_id'],session.stream['completed_count'],session.stream['partial_seconds'],'reset' if reset else 'interrupted')
            if reset:
                new_journal=SessionLog(ROOT,self.config,key,session.scenario_id,session.profile['name'])
                session.journal.append('session_ended',reason='reset',generation=session.generation,
                                       next_archive_id=new_journal.archive_id)
                session.journal=new_journal
            else:
                session.journal.append('interrupted',generation=session.generation,
                                       reply_in_progress=session.busy)
            session.generation += 1
            session.busy = False
            if reset:
                session.history.clear()
                session.memory.clear()
                session.stream=None
                session.recent_gestures.clear()
                initial = session.profile.get('initial_state', {'emotion': 'neutral', 'intensity': .5})
                session.emotion, session.intensity = initial['emotion'], initial['intensity']
                session.relationship = initial_relationship(session.profile)
        return {'ok': True,'relationship':session.relationship,'generation':session.generation}

    def assert_current(self, key, generation):
        with self.lock:
            if key not in self.sessions or self.sessions[key].generation != generation:
                raise StaleTurn('Turn was interrupted or reset')

    def appraise(self, text, history, relationship, profile, recalled=None):
        if self.config['dialogue_provider'] != 'llama.cpp':
            return {'event': 'neutral', 'invites_detail': False}
        recent = []
        for message in history[-8:]:
            content = message['content']
            if message['role'] == 'assistant':
                content = ' '.join(s['text'] for s in json.loads(content)['segments'])
            recent.append({'role': message['role'], 'content': content})
        body = {'model': self.config['llm_model'], 'stream': False, 'temperature': 0,
                'max_tokens': 100, 'chat_template_kwargs': {'enable_thinking': False},
                'messages': [{'role': 'system', 'content': APPRAISAL_PROMPT +
                    '\nPatient context: ' + profile['setting'] + '\n' + profile['facts'][0] +
                    '\nPrevious interaction state: ' + json.dumps(relationship)}] +
                    recent + [{'role': 'user', 'content': text}],
                'response_format': {'type': 'json_schema', 'json_schema': {
                    'name': 'interaction_appraisal', 'strict': True, 'schema': APPRAISAL_SCHEMA}}}
        self.fit_context(body, recalled=recalled)
        data = self.post_json(self.config['llm_url'], body, self.config['llm_timeout_seconds'])
        return validate_appraisal(data['choices'][0]['message'].get('content', ''))

    def fit_context(self, body, recalled=None):
        """Reserve output tokens before generation, rather than accepting truncated JSON."""
        url = urllib.parse.urlsplit(self.config['llm_url'])
        base = urllib.parse.urlunsplit((url.scheme, url.netloc, '', '', ''))
        if self.context_limit is None:
            with urllib.request.urlopen(base + '/props', timeout=5) as response:
                self.context_limit = int(json.load(response)['default_generation_settings']['n_ctx'])
        base_system = body['messages'][0]['content']
        selected = list(recalled or [])
        while True:
            body['messages'][0]['content'] = base_system + memory_prompt(selected)
            template = self.post_json(base + '/apply-template', {
                'messages': body['messages'], 'add_generation_prompt': True,
                'chat_template_kwargs': {'enable_thinking': False}}, 5)['prompt']
            tokens = self.post_json(base + '/tokenize', {
                'content': template, 'add_special': True, 'parse_special': True}, 5)['tokens']
            if len(tokens) + body['max_tokens'] + 32 <= self.context_limit:
                return selected
            if len(body['messages']) <= 2:
                if selected:
                    selected.pop()  # Retrieval order is most relevant first.
                    continue
                raise ContractError('Message and character context are too long. Please shorten the message.')
            # Drop oldest complete user/assistant pairs, never system rules/current utterance.
            del body['messages'][1:3]

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
        relationship = state.get('relationship')
        fuller = wants_fuller_reply(relationship)
        system = character_prompt(profile, self.config.get('conversation_language'), relationship)
        system += '\nReturn only a JSON object with a segments array. Every segment has text, emotion, intensity (0-1), gesture, voice_style, gaze, transition_seconds, pause_before_seconds, hold_after_seconds, gesture_at and gesture_duration_seconds.'
        system += '\nAllowed gestures: '+', '.join(GESTURES)+'; voices: '+', '.join(VOICES)+'; gaze: '+', '.join(GAZES)+'.'
        system += '\nCurrent simulated delivery state: ' + json.dumps({k:v for k,v in state.items() if k not in ('relationship','recalled','memory_used')})
        system += PATIENT_PERFORMANCE_PROMPT if state.get('relationship') else PERFORMANCE_PROMPT
        language_guidance = conversation_guidance(self.config.get('conversation_language'), patient=bool(relationship))
        system += language_guidance
        system += '\nAvailable delivery states: ' + json.dumps({e['name']:e['description'] for e in EMOTION_CATALOG['emotions']})
        if relationship:
            system += relationship_prompt(relationship, profile)
        recent = history[-8:]
        if relationship:
            # Past animation timings consume context without adding conversational memory.
            # Keep the actual dialogue; current delivery and rapport are supplied above.
            recent = [{'role': m['role'], 'content': (' '.join(s['text'] for s in json.loads(m['content'])['segments'])
                       if m['role'] == 'assistant' else m['content'])} for m in recent]
        body = {
            'model': self.config['llm_model'],
            'messages': [{'role': 'system', 'content': system}] + recent + [{'role': 'user', 'content': text}],
            'stream': False, 'temperature': .7, 'top_p': .8, 'top_k': 20, 'max_tokens': 850,
            'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'alex_reply', 'strict': True, 'schema': SEGMENT_SCHEMA}},
        }
        for attempt in range(3):
            if relationship:
                # Rebuild from the original instructions on retry, so memory is
                # never duplicated by a second context-budget pass.
                state['memory_used'] = self.fit_context(body, recalled=state.get('recalled')) or []
            data = self.post_json(self.config['llm_url'], body, self.config['llm_timeout_seconds'])
            segments = validate_reply(data['choices'][0]['message'].get('content', ''))
            if self.config.get('conversation_language') == 'cnr' and obvious_english_leak(' '.join(s['text'] for s in segments)):
                if attempt == 2:
                    raise ContractError('Reply switched languages. Please try again.')
                body['messages'][0]['content'] = system + '\nRewrite the reply entirely in Montenegrin Latin script. No English clauses, including short denials or emotional reactions. Keep the meaning, character facts and word limit.'
                continue
            words = sum(len(s['text'].split()) for s in segments)
            if fuller and words < 30 and attempt == 0:
                body['messages'][0]['content'] = system + '\nYour first draft was too terse for the question. Give 3-5 connected sentences, about 40-80 words within word_limit, explaining a concrete relevant detail and your own perspective. Discuss the requested topic, not a repeated symptom. A genuine sensitive refusal can remain brief.'
                continue
            if not relationship or words <= relationship['word_limit']:
                return segments
            body['messages'][0]['content'] = system + '\nYour previous attempt was too long. Respond in at most ' + str(relationship['word_limit']) + ' spoken words total.'
        raise ContractError('Reply exceeded this patient’s current disclosure limit. Try again.')

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

    def turn(self, key, text, opening=False, stream=None):
        if not isinstance(text, str) or len(text) > 2000 or (not opening and not text.strip()):
            raise ContractError('Enter 1–2000 characters')
        with self.lock:
            session = self.sessions[key]
            if stream and (stream['closed'] or stream is not session.stream or stream['generation']!=session.generation):
                raise StaleTurn('Turn was interrupted or reset')
            if session.stream and not session.stream['closed'] and stream is not session.stream:
                raise ContractError('A streaming reply is already in progress')
            if session.busy:
                raise ContractError('A reply is already in progress')
            if session.relationship and session.relationship['status'] == 'ended':
                raise ContractError('This patient ended the session. Start a new conversation.')
            request_id=uuid.uuid4().hex
            journal=session.journal
            journal.append('turn_started',request_id=request_id,generation=session.generation,
                           opening=bool(opening),text='' if opening else text.strip(),
                           playback_mode='acknowledged_sentences' if stream else 'legacy',
                           turn_id=stream['turn_id'] if stream else None)
            session.busy = True
            generation = session.generation
            history = list(session.history)
            state = {'emotion': session.emotion, 'intensity': session.intensity}
            # New dictionaries only: interruption/failure must not partially advance rapport.
            relationship = dict(session.relationship) if session.relationship else None
            profile = session.profile
            recalled = select_memories(session.memory, text, history)
            memory = list(session.memory)
            recent_gestures=list(session.recent_gestures)
        started = time.perf_counter()
        created_files = []
        committed = False
        try:
            # A cancelled request can finish remotely, but cannot publish audio/history.
            with self.inference_lock:
                self.assert_current(key, generation)
                if relationship and not opening:
                    appraisal = self.appraise(text.strip(), history, relationship, profile, recalled)
                    self.assert_current(key, generation)
                    relationship = advance(relationship, appraisal, profile)
                if stream:
                    with self.lock:
                        self.assert_current(key,generation)
                        stream['relationship']=dict(relationship) if relationship else None
                if relationship:
                    state['relationship'] = relationship
                state['recalled'] = recalled
                if relationship and relationship['status'] == 'ended':
                    segments = ending_segments(relationship, profile, self.config.get('conversation_language'))
                else:
                    segments = self.generate(text.strip(), history, opening, state, profile)
                segments = validate_reply({'segments': segments})
                if relationship and not opening:
                    segments = enforce_boundary_cues(segments, relationship, profile)
                segments = refine_delivery(segments,state,recent_gestures)
                if stream:segments=sentence_segments(segments)
            self.assert_current(key, generation)
            generation_ms = round((time.perf_counter() - started) * 1000)
            turn_id = stream['turn_id'] if stream else uuid.uuid4().hex
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
                    if stream:
                        if segment['audio_url']:
                            with wave.open(str(self.runtime/(audio_id+'.wav'))) as audio:
                                segment['audio_duration_seconds']=audio.getnframes()/audio.getframerate()
                        with self.lock:
                            self.assert_current(key,generation)
                            elapsed=round((time.perf_counter()-stream['started'])*1000)
                            journal.append('segment_ready',turn_id=turn_id,index=i,segment=segment,ready_ms=elapsed)
                            stream['segments'].append(dict(segment))
                            if stream['first_audio_ms'] is None:stream['first_audio_ms']=elapsed
            self.assert_current(key, generation)
            with self.lock:
                self.assert_current(key, generation)
                response = {'turn_id': turn_id, 'session_id': key, 'segments': segments,
                    'generation_ms': generation_ms, 'speech_ms': speech_ms, 'alignment_ms': alignment_ms,
                    'total_ms': round((time.perf_counter() - started) * 1000),
                    'dialogue_provider': self.config['dialogue_provider'], 'tts_provider': self.config['tts_provider'],
                    'relationship': dict(relationship) if relationship else None,
                    'memory': {'retained_turns':min(len(memory)+1,MAX_TURNS), 'recalled':recalled,
                               'in_reply_context':state.get('memory_used',[])}}
                journal.append('turn_completed',request_id=request_id,generation=generation,
                               response=response,session_ended=bool(relationship and relationship['status']=='ended'))
                if stream:
                    # Playback acknowledgements, not generation, commit conversation state.
                    committed=True
                    return response
                session.history += [{'role': 'user', 'content': '[Start the session]' if opening else text.strip()},
                                    {'role': 'assistant', 'content': json.dumps({'segments': [
                                        {k: s[k] for k in FIELDS} for s in segments]})}]
                session.history = session.history[-12:]
                session.emotion, session.intensity = segments[-1]['emotion'], segments[-1]['intensity']
                session.relationship = relationship
                session.memory = remember(memory, text.strip(), segments, relationship, opening)
                session.recent_gestures=(session.recent_gestures+[s['gesture'] for s in segments])[-6:]
                committed = True
            return response
        except Exception as exc:
            try:
                journal.append('turn_cancelled' if isinstance(exc,StaleTurn) else 'turn_failed',
                               request_id=request_id,generation=generation,error_type=type(exc).__name__)
            except SessionLogError:
                pass  # Preserve the original error; turn_started remains the durable pending record.
            raise
        finally:
            if not committed:
                for path in created_files:
                    published=stream and any(s.get('audio_url')=='/audio/'+path.name for s in stream['segments'])
                    if not published:path.unlink(missing_ok=True)
            with self.lock:
                if session.generation == generation and not stream:
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
            language = whisper_language(self.config.get('stt_language', 'en'))
            if language and language != 'en' and not self.stt.model.is_multilingual:
                raise ContractError('This STT language requires a multilingual model; replace small.en with small.')
            options = {key: self.config['stt_' + key]
                       for key in ('initial_prompt', 'condition_on_previous_text')
                       if 'stt_' + key in self.config}
            segments, _ = self.stt.transcribe(io.BytesIO(raw), language=language,
                                             task='transcribe', vad_filter=True, **options)
            text = ' '.join(s.text.strip() for s in segments).strip()
            if self.config.get('stt_output_script') == 'latin':
                text = latin_script(text)
            return {'text': text}

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
                    'sentence_streaming': True,
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
                elif self.path == '/turn/start':
                    value=bridge.start_stream(body['session_id'],body.get('text',''),body.get('opening') is True,body.get('expected_generation'))
                elif self.path == '/turn/poll':
                    value=bridge.poll_stream(body['session_id'],body['turn_id'])
                elif self.path == '/playback':
                    value=bridge.acknowledge(body['session_id'],body['turn_id'],body['completed_count'],body.get('partial_seconds',0.))
                elif self.path == '/turn/finish':
                    value=bridge.finish_stream(body['session_id'],body['turn_id'],body['completed_count'],body.get('partial_seconds',0.),'interrupted' if body.get('interrupted') else 'completed')
                elif self.path in ('/interrupt', '/reset'):
                    if body.get('turn_id'):
                        bridge.acknowledge(body['session_id'],body['turn_id'],body.get('completed_count',0),body.get('partial_seconds',0.))
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
