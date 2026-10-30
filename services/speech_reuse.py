"""Exact recorded-line playback and bounded local WAV/lip-sync reuse.

Never select a merely similar sentence. A miss uses normal live synthesis.
Generated cache files contain audio and timing data, not dialogue metadata.
"""
import hashlib
import io
import json
from importlib import metadata
from pathlib import Path
import unicodedata
import uuid
import wave


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text_key(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def wav_duration(data):
    if not 44 <= len(data) <= 5_000_000:
        raise ValueError('Recorded speech must be a bounded WAV')
    with wave.open(io.BytesIO(data)) as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != 'NONE':
            raise ValueError('Recorded speech must be mono PCM16')
        rate = wav.getframerate()
        if not 1 <= rate <= 192000:
            raise ValueError('Invalid speech sample rate')
        duration = wav.getnframes() / rate
        if not .2 <= duration <= 45:
            raise ValueError('Recorded speech must last 0.2-45 seconds')
        if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
            raise ValueError('Incomplete speech WAV')
    return duration


class SpeechReuse:
    def __init__(self, root, config, cast):
        self.root = Path(root).resolve()
        self.config = config
        self.cast = cast
        self.enabled = config.get('tts_provider') == 'higgs' or (
            config.get('tts_provider') == 'kokoro' and config.get('speech_cache_enabled', False))
        self.cache_enabled = self.enabled and config.get('speech_cache_enabled', False)
        self.directory = self.root / 'services/.runtime/speech-cache'
        self.limit = config.get('speech_cache_max_mib', 256)
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or not 8 <= self.limit <= 2048:
            raise ValueError('speech_cache_max_mib must be 8-2048')
        self.recordings = {}
        if config.get('tts_provider') == 'higgs' and config.get('recorded_speech_enabled', False):
            manifest = self.root / 'voices/recorded/manifest.json'
            if manifest.is_file():
                data = json.loads(manifest.read_text(encoding='utf-8'))
                if data.get('version') != 1 or not isinstance(data.get('clips'), list):
                    raise ValueError('Invalid recorded speech library')
                for clip in data['clips']:
                    scenario = clip['scenario_id']
                    if clip.get('approved') is not True or cast.scenarios.get(scenario) != clip['speaker']:
                        raise ValueError('Recorded clip must have approved, assigned speaker')
                    path = (self.root / clip['audio']).resolve()
                    if not path.is_relative_to(self.root / 'voices/recorded'):
                        raise ValueError('Recorded clips must stay inside voices/recorded')
                    key = (scenario, clip['emotion'], text_key(clip['text']))
                    if key in self.recordings:
                        raise ValueError('Duplicate recorded speech line')
                    self.recordings[key] = dict(clip, path=path)
        self._engine = None

    def recording(self, segment, scenario=None):
        if self.config.get('tts_provider') != 'higgs':
            return None
        return self.recordings.get((scenario or segment.get('scenario_id'),
            segment['emotion'], text_key(segment['text'])))

    def engine(self):
        if self._engine is None:
            fingerprints = []
            # Content hashes for generation code/config; file identity for large
            # pinned weights avoids rereading gigabytes on every service launch.
            if self.config.get('tts_provider') == 'kokoro':
                paths = [self.root / name for name in ('services/alex_service.py', 'services/speech_reuse.py',
                    '.cache/kokoro/kokoro-v1.0.onnx', '.cache/kokoro/voices-v1.0.bin')]
                for package in ('kokoro-onnx', 'onnxruntime', 'phonemizer', 'espeakng-loader'):
                    try:version = metadata.version(package)
                    except metadata.PackageNotFoundError:version = None
                    fingerprints.append([package, version])
            else:
                names = ['services/higgs_service.py', 'services/performance_contract.py',
                    'services/speech_audio.py', 'services/speech_language.py', 'services/higgs_decode.py']
                model = (self.root / self.config.get('higgs_model', '.cache/higgs-transformers')).resolve()
                codec = self.root / '.cache/higgs-audio-v2-tokenizer'
                paths = [self.root / n for n in names]
                for directory in (model, codec):
                    if directory.is_dir():
                        paths.extend(p for p in directory.iterdir() if p.is_file())
            for path in sorted(paths):
                if path.is_file():
                    stat = path.stat()
                    identity = hashlib.sha256(path.read_bytes()).hexdigest() if stat.st_size < 2_000_000 else [stat.st_size, stat.st_mtime_ns]
                    fingerprints.append([str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path), identity])
            self._engine = digest(fingerprints)
        return self._engine

    def key(self, segment, use_recording=True):
        scenario = segment.get('scenario_id')
        if self.config.get('tts_provider') == 'kokoro':
            # Match the bridge's local Kokoro synthesis parameters exactly.
            # This namespace never resolves a cloned-voice recipe or recording.
            return digest(['generated-kokoro-v1', self.engine(), self.config.get('tts_model', 'kokoro'),
                self.config.get('tts_voice'), 'en-us', .95, scenario, segment['text'],
                segment['emotion'], segment.get('voice_style'), segment.get('intensity')])
        clip = self.recording(segment) if use_recording else None
        if clip:
            return digest(['recorded-v1', scenario, clip['speaker'], segment['emotion'],
                text_key(segment['text']), clip['sha256']])
        recipe = self.cast.resolve(scenario, segment) if scenario else None
        shared = self.root / self.config.get('higgs_reference', 'voices/reference.wav')
        reference = None if recipe else hashlib.sha256(shared.read_bytes()).hexdigest()
        transcript = None if recipe else shared.with_suffix('.json').read_text(encoding='utf-8')
        return digest(['generated-v1', self.engine(), recipe, reference, transcript,
            {k: self.config.get(k) for k in ('higgs_quantization', 'higgs_allow_quantized_cast', 'higgs_temperature', 'higgs_pronunciation', 'higgs_fast_decode', 'higgs_sentence_streaming')},
            scenario, text_key(segment['text']), segment['emotion'], segment.get('voice_style'), segment.get('intensity')])

    def get(self, key):
        if not self.cache_enabled:
            return None

        try:
            path = self.directory / (key + '.wav')
            metadata_path = self.directory / (key + '.json')
            if not 44 <= path.stat().st_size <= 5_000_000 or metadata_path.stat().st_size > 500_000:
                return None
            meta = json.loads(metadata_path.read_text(encoding='utf-8'))
            audio = path.read_bytes()
            if meta['audio_sha256'] != hashlib.sha256(audio).hexdigest():
                return None
            wav_duration(audio)
            path.touch()
            return dict(meta, audio=audio, source='cache')
        except (OSError, ValueError, KeyError, TypeError, wave.Error, EOFError):
            return None

    def lookup(self, segment):
        key = self.key(segment)
        asset = self.get(key)
        clip = self.recording(segment)
        if clip and asset and hashlib.sha256(asset['audio']).hexdigest() != clip['sha256']:
            asset = None
        if asset is None:
            asset = self.recorded_audio(segment)
            if asset is None and clip:
                # Never file a regenerated fallback under the original recording hash.
                key = self.key(segment, use_recording=False)
                asset = self.get(key)
        return key, asset

    def recorded_audio(self, segment):
        clip = self.recording(segment)
        if not clip:
            return None
        try:
            path = clip['path']
            if not 44 <= path.stat().st_size <= 5_000_000:
                return None
            audio = path.read_bytes()
            if hashlib.sha256(audio).hexdigest() != clip['sha256']:
                return None
            wav_duration(audio)
            return dict(audio=audio, source='recorded')
        except (OSError, ValueError, wave.Error, EOFError):
            return None

    def put(self, key, audio, cues, source, alignment_key):
        if not self.cache_enabled:
            return
        try:
            wav_duration(audio)
            self.directory.mkdir(parents=True, exist_ok=True)
            metadata = dict(audio_sha256=hashlib.sha256(audio).hexdigest(),
                mouth_cues=cues, lip_sync_source=source, alignment_key=alignment_key)
            for suffix, data in [('.wav', audio), ('.json', json.dumps(metadata).encode())]:
                temporary = self.directory / (uuid.uuid4().hex + '.tmp')
                try:
                    temporary.write_bytes(data)
                    temporary.replace(self.directory / (key + suffix))
                finally:
                    temporary.unlink(missing_ok=True)
            files = sorted(self.directory.glob('*.wav'), key=lambda p: p.stat().st_mtime, reverse=True)
            used = 0
            for index, path in enumerate(files):
                used += path.stat().st_size + path.with_suffix('.json').stat().st_size
                if used > self.limit * 1024**2 or index >= 512:
                    path.unlink(missing_ok=True)
                    path.with_suffix('.json').unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, wave.Error, EOFError):
            # A cache failure must never prevent a valid newly generated reply.
            pass

    def alignment_key(self):
        executable = self.root / self.config.get('rhubarb_path', '.tools/rhubarb/Rhubarb-Lip-Sync-1.14.0-Windows/rhubarb.exe')
        identity = [executable.stat().st_size, executable.stat().st_mtime_ns] if executable.is_file() else None
        return digest(['alignment-v1', self.config.get('lip_sync_provider'),
            self.config.get('conversation_language'), identity])
