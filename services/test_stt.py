import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import wave

from alex_service import Bridge, ContractError
from speech_language import latin_script


class SpeechLanguageTests(unittest.TestCase):
    def setUp(self):
        config = json.loads(Path(__file__).with_name('config.example.json').read_text())
        config['stt_provider'] = 'faster-whisper'
        config.pop('stt_language', None)
        self.bridge = Bridge(config)
        self.bridge.stt = Mock()
        self.bridge.stt.model.is_multilingual = True
        self.bridge.stt.transcribe.return_value = ([SimpleNamespace(text=' Želim da razgovaramo. ')], None)
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as recording:
            recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            recording.writeframes(b'\0\0' * 8000)
        self.audio = base64.b64encode(audio.getvalue()).decode()

    def test_legacy_config_keeps_english(self):
        self.bridge.transcribe(self.audio)
        self.assertEqual(self.bridge.stt.transcribe.call_args.kwargs['language'], 'en')

    def test_regional_speech_is_transcribed_without_translation_or_text_rewriting(self):
        self.bridge.config['stt_language'] = 'sr'
        result = self.bridge.transcribe(self.audio)
        self.assertEqual(result['text'], 'Želim da razgovaramo.')
        self.assertEqual(self.bridge.stt.transcribe.call_args.kwargs,
                         {'language': 'sr', 'task': 'transcribe', 'vad_filter': True})

    def test_auto_lets_model_detect_language(self):
        self.bridge.config['stt_language'] = 'auto'
        self.bridge.transcribe(self.audio)
        self.assertIsNone(self.bridge.stt.transcribe.call_args.kwargs['language'])

    def test_montenegrin_alias_uses_supported_whisper_token(self):
        self.bridge.config['stt_language'] = 'cnr'
        self.bridge.transcribe(self.audio)
        self.assertEqual(self.bridge.stt.transcribe.call_args.kwargs['language'], 'sr')

    def test_optional_latin_script_preserves_negation_numbers_and_diacritics(self):
        source = 'Његош: Не боли ме. Чекам већ ћерку, ђака и Џемала. ЉУТЊА!'
        self.bridge.stt.transcribe.return_value = ([SimpleNamespace(text=source)], None)
        # Legacy callers retain the recognizer's script.
        self.assertEqual(self.bridge.transcribe(self.audio)['text'], source)
        self.bridge.config['stt_output_script'] = 'latin'
        self.assertEqual(self.bridge.transcribe(self.audio)['text'],
                         'Njegoš: Ne boli me. Čekam već ćerku, đaka i Džemala. LJUTNJA!')
        latin = 'Ne uzimam 2 tablete. Ni č ni ć; e-mail: test@example.com.'
        self.assertEqual(latin_script(latin), latin)

    def test_vad_empty_transcript_stays_empty(self):
        self.bridge.config['stt_output_script'] = 'latin'
        self.bridge.stt.transcribe.return_value = (iter([]), None)
        self.assertEqual(self.bridge.transcribe(self.audio), {'text': ''})

    def test_configured_prompt_and_independent_decoding_reach_whisper(self):
        self.bridge.config.update(stt_initial_prompt='Razgovor na crnogorskom jeziku, latinicom.',
                                  stt_condition_on_previous_text=False)
        self.bridge.transcribe(self.audio)
        options = self.bridge.stt.transcribe.call_args.kwargs
        self.assertFalse(options['condition_on_previous_text'])
        self.assertEqual(options['initial_prompt'], self.bridge.config['stt_initial_prompt'])
        self.assertTrue(options['vad_filter'])
        self.assertEqual(options['task'], 'transcribe')

    def test_english_only_model_cannot_silently_ignore_regional_language(self):
        self.bridge.config['stt_language'] = 'sr'
        self.bridge.stt.model.is_multilingual = False
        with self.assertRaisesRegex(ContractError, 'multilingual'):
            self.bridge.transcribe(self.audio)
        self.bridge.stt.transcribe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
