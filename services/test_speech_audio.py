import unittest
import io
import threading
from contextlib import nullcontext
from unittest.mock import Mock
import numpy as np
from alex_service import validate_reply
from speech_audio import audio_quality, checked_synthesis


RATE = 1000

def speech(seconds=1):
    return .1 * np.sin(np.arange(round(seconds * RATE)) * .2)


class SpeechAudioTests(unittest.TestCase):
    def segment(self, text='Prva rečenica. Druga rečenica.'):
        return validate_reply({'segments': [dict(text=text, emotion='sad', intensity=.6)]})[0]

    def test_ordinary_pauses_do_not_regenerate(self):
        audio = np.concatenate([speech(), np.zeros(700), speech()])
        calls = []
        def render(part, retry):
            calls.append(retry)
            return audio
        result, report = checked_synthesis(self.segment(), render, RATE)
        np.testing.assert_array_equal(result, audio.astype(np.float32))
        self.assertEqual(calls, [False])
        self.assertFalse(report['regenerated'])

    def test_failed_tail_regenerates_all_sentences_with_emotion(self):
        calls = []
        def render(part, retry):
            calls.append((part, retry))
            return speech() if retry else np.concatenate([speech(), np.zeros(5000)])
        result, report = checked_synthesis(self.segment(), render, RATE)
        self.assertTrue(report['regenerated'])
        self.assertEqual([p['text'] for p, r in calls if r], ['Prva rečenica.', 'Druga rečenica.'])
        self.assertTrue(all(p['emotion'] == 'sad' and p['intensity'] == .6 for p, r in calls))
        self.assertEqual(len(result), 2250)

    def test_failed_retry_is_not_published(self):
        with self.assertRaisesRegex(ValueError, 'regeneration failed'):
            checked_synthesis(self.segment(), lambda p, r: np.zeros(5000), RATE)

    def test_single_sentence_retry(self):
        calls = []
        def render(part, retry):
            calls.append(retry)
            return speech() if retry else np.array([np.nan])
        _, report = checked_synthesis(self.segment('Samo jedna rečenica.'), render, RATE)
        self.assertEqual(calls, [False, True])
        self.assertEqual(report['sentences'], 1)

    def test_retry_budget(self):
        calls = []
        def render(part, retry):
            calls.append(retry)
            return np.zeros(4000)
        with self.assertRaisesRegex(ValueError, 'budget'):
            checked_synthesis(self.segment('Jedan. Dva. Tri. Četiri. Pet.'), render, RATE)
        self.assertEqual(calls, [False])

    def test_invalid_audio_and_long_internal_gap(self):
        for audio in [[], [np.nan], [np.inf], np.zeros(5000), np.concatenate([speech(), np.zeros(4000), speech()])]:
            self.assertFalse(audio_quality(audio, RATE)['ok'])

    def test_worker_returns_complete_retry_wav_and_releases_lock(self):
        import soundfile as sf
        from higgs_service import HiggsVoice
        voice = HiggsVoice.__new__(HiggsVoice)
        voice.lock = threading.Lock()
        voice.config = {'higgs_temperature': .6}
        voice.rate = RATE
        voice.reference_codes = 'same speaker'
        voice.reference_text = 'Verbatim recording transcript.'
        voice.tokenizer = object()
        voice.torch = Mock()
        voice.torch.inference_mode.side_effect = nullcontext
        voice.model = Mock()
        arrays = [np.concatenate([speech(), np.zeros(5000)]), speech(), speech()]
        voice.model.generate_speech.side_effect = [Mock(numpy=Mock(return_value=a)) for a in arrays]
        wav = voice.synthesize(self.segment())
        audio, rate = sf.read(io.BytesIO(wav))
        self.assertEqual(rate, RATE)
        self.assertEqual(len(audio), 2250)
        self.assertFalse(voice.lock.locked())
        calls = voice.model.generate_speech.call_args_list
        self.assertEqual([c.kwargs['temperature'] for c in calls], [.6, .5, .5])
        self.assertTrue(all(c.kwargs['reference_codes'] == 'same speaker' for c in calls))
        voice.model.generate_speech.side_effect = RuntimeError('generation failed')
        with self.assertRaises(RuntimeError):
            voice.synthesize(self.segment())
        self.assertFalse(voice.lock.locked())


if __name__ == '__main__':
    unittest.main()
