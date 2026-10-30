"""Trusted local scenario-to-speaker routing; request bodies never supply file paths."""
import hashlib
import json
from pathlib import Path

EMOTION_RECIPES = {'angry': 'anger', 'sad': 'sadness', 'happy': 'happiness',
                  'despondent': 'low_energy', 'numb': 'low_energy',
                  'panicked': 'afraid', 'calm': 'neutral'}

class VoiceCast:
    def __init__(self, root, sentence_streaming=False):
        if not isinstance(sentence_streaming, bool):
            raise ValueError('higgs_sentence_streaming must be true or false')
        self.sentence_streaming = sentence_streaming
        self.root = Path(root).resolve()
        path = self.root / 'voices/cast.json'
        self.scenarios = {}
        self.speakers = {}
        if not path.exists(): return  # Older portable packs retain the shared voice.
        cast = json.loads(path.read_text(encoding='utf-8'))
        self.scenarios = cast['scenarios']
        for speaker, manifest in cast['speakers'].items():
            data = json.loads(self.path(manifest).read_text(encoding='utf-8'))
            if data['speaker'] != speaker or data['precision'] != 'bf16':
                raise ValueError('Invalid voice pack identity or precision')
            for recipe in data['recipes'].values():
                reference = self.path(recipe['reference'])
                if hashlib.sha256(reference.read_bytes()).hexdigest() != recipe['reference_sha256']:
                    raise ValueError('Voice reference differs from approved pack: ' + str(reference))
            if 'neutral' not in data['recipes']: raise ValueError('Voice pack needs neutral fallback')
            self.speakers[speaker] = data['recipes']
        if not set(self.scenarios.values()) <= self.speakers.keys():
            raise ValueError('Scenario voice pack missing')

    def path(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root / 'voices'):
            raise ValueError('Voice assets must stay inside voices')
        return path

    def resolve(self, scenario, segment):
        if scenario is None or not self.scenarios: return None
        if not isinstance(scenario, str) or scenario not in self.scenarios:
            raise ValueError('Unknown voice scenario')
        speaker = self.scenarios[scenario]
        recipes = self.speakers[speaker]
        emotion = EMOTION_RECIPES.get(segment['emotion'], segment['emotion'])
        # Unreviewed emotions keep this speaker's neutral identity. Never fall
        # through to another person's recording or add unapproved global tags.
        recipe = recipes.get(emotion, recipes['neutral'])
        resolved = dict(recipe, speaker=speaker)
        if self.sentence_streaming:
            resolved['mode'] = 'sentences'
        return resolved

    def apply_stream_pauses(self, scenario, segments):
        for index, segment in enumerate(segments):
            recipe = self.resolve(scenario, segment)
            if index and recipe and recipe['mode'] == 'sentences':
                segment['pause_before_seconds'] = max(segment['pause_before_seconds'], recipe['sentence_gap_seconds'])

    def delivery_segments(self, scenario, segments):
        """Preserve auditioned phrasing; split only presets approved that way.

        Playback acknowledgements still apply to complete audio segments. An
        interrupted multi-sentence beat is conservatively unconfirmed; we never
        infer heard words from a fraction of its audio duration.
        """
        from streaming_turns import sentence_segments
        result = []
        for segment in segments:
            recipe = self.resolve(scenario, segment)
            if recipe and recipe['mode'] != 'sentences':
                result.append(dict(segment))
            else:
                result.extend(sentence_segments([segment]))
        return result
