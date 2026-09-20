import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from alex_service import ContractError, ROOT
from emotion_audition import AuditionBridge


class AuditionTests(unittest.TestCase):
    def setUp(self):
        runtime = ROOT / 'services/.runtime'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='audition-test-', dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.assertTrue(self.folder.resolve().is_relative_to(runtime.resolve()))
        cases = []
        for index, (key, emotion, style) in enumerate([
                ('neutral', 'neutral', 'normal'), ('angry', 'angry', 'tense'), ('closer', 'angry', 'subdued')]):
            path = self.folder / (key + '.wav')
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                wav.writeframes(bytes([index + 1, 0]) * 8000)
            cases.append({'id': key, 'audio': path.relative_to(ROOT).as_posix(),
                          'segment': {'text': 'The same words.', 'emotion': emotion,
                                      'intensity': .8, 'gesture': 'none', 'voice_style': style}})
        self.manifest = {'cases': cases}
        config = json.loads((ROOT / 'services/config.example.json').read_text())
        self.bridge = AuditionBridge(config, self.manifest, prepare=False)
        self.bridge.runtime = self.folder

    def generate(self, text):
        return self.bridge.generate(text, [], False, {}, {})

    def test_comparison_keeps_order_and_uses_the_correct_angry_variant(self):
        segments = self.generate('Please compare.')
        self.assertEqual([s['voice_style'] for s in segments], ['normal', 'tense', 'subdued'])
        for index, segment in enumerate(segments):
            audio_id = f'{index:032x}'
            url = self.bridge.synthesize(segment, audio_id)
            source = ROOT / self.manifest['cases'][index]['audio']
            output = self.folder / url.rsplit('/', 1)[1]
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(output.read_bytes()).digest())

    def test_unrecognized_command_never_speaks_an_unrelated_fixture(self):
        with self.assertRaises(ContractError):
            self.generate('How was your day?')

    def test_regional_commands_support_latin_diacritics_and_cyrillic(self):
        for command in ('Uporedi.', 'Molim vas, uporedite.', 'Упореди.'):
            with self.subTest(command=command):
                self.assertEqual(len(self.generate(command)), 3)
        for command, style in [('Neutralno.', 'normal'), ('Ljutito!', 'tense'),
                               ('Blaže.', 'subdued'), ('Блаже.', 'subdued')]:
            with self.subTest(command=command):
                self.assertEqual(self.generate(command)[0]['voice_style'], style)
        with self.assertRaises(ContractError):
            self.generate('Osjećam se neutralnostvarno.')

    def test_commands_do_not_mutate_case_and_closer_uses_same_body_intensity(self):
        result = self.generate('Play closer.')[0]
        self.assertEqual(result['intensity'], self.generate('angry')[0]['intensity'])
        result['text'] = 'Modified'
        self.assertEqual(self.generate('closer')[0]['text'], 'The same words.')

    def test_response_uses_existing_unity_audio_protocol(self):
        session = self.bridge.new_session()
        reply = self.bridge.turn(session['session_id'], 'angry')
        self.assertEqual(reply['tts_provider'], 'higgs-recorded')
        self.assertEqual(reply['dialogue_provider'], 'controlled-audition')
        self.assertEqual(reply['segments'][0]['emotion'], 'angry')
        self.assertTrue((self.folder / reply['segments'][0]['audio_url'].rsplit('/', 1)[1]).is_file())
        self.bridge.invalidate(session['session_id'], reset=True)
        self.assertEqual(self.bridge.sessions[session['session_id']].history, [])


if __name__ == '__main__':
    unittest.main()
