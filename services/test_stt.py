import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import wave

from alex_service import Bridge, ContractError


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

    def test_english_only_model_cannot_silently_ignore_regional_language(self):
        self.bridge.config['stt_language'] = 'sr'
        self.bridge.stt.model.is_multilingual = False
        with self.assertRaisesRegex(ContractError, 'multilingual'):
            self.bridge.transcribe(self.audio)
        self.bridge.stt.transcribe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
