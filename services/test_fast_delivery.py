import json
import unittest
from unittest.mock import Mock

from alex_service import Bridge, ContractError, ROOT, COMPACT_FIELDS, COMPACT_SEGMENT_SCHEMA, SEGMENT_SCHEMA
from performance_contract import FIELDS, TIMING_DEFAULTS


class FastDeliveryTests(unittest.TestCase):
    def bridge(self, **settings):
        config = json.loads((ROOT / 'services/config.example.json').read_text())
        config.update(settings)
        return Bridge(config)

    def test_compact_model_directions_keep_semantics_and_receive_local_timings(self):
        bridge = self.bridge(dialogue_provider='llama.cpp', tts_provider='none', llm_compact_delivery=True)
        planned = dict(text='I am still worried.', emotion='anxious', intensity=.55,
                       gesture='glance_away', voice_style='hesitant', gaze='away')
        captured = []
        bridge.post_json = lambda url, body, timeout: (captured.append(body) or
            {'choices': [{'message': {'content': json.dumps({'segments': [planned]})}}]})
        reply = bridge.generate('How do you feel?', [], False, {}, bridge.profiles['alex-earthquake'])[0]
        self.assertEqual({k: reply[k] for k in planned}, planned)
        self.assertEqual(set(reply), set(FIELDS))
        self.assertEqual({k: reply[k] for k in TIMING_DEFAULTS}, TIMING_DEFAULTS)
        schema = captured[0]['response_format']['json_schema']['schema']
        self.assertEqual(schema, COMPACT_SEGMENT_SCHEMA)
        self.assertEqual(set(schema['properties']['segments']['items']['required']), set(COMPACT_FIELDS))
        self.assertNotIn('transition_seconds', captured[0]['messages'][0]['content'])
        self.assertIn('maps animation timing locally', captured[0]['messages'][0]['content'])

    def test_full_schema_still_contains_all_timing_fields(self):
        self.assertEqual(set(SEGMENT_SCHEMA['properties']['segments']['items']['required']), set(FIELDS))
        self.assertFalse(SEGMENT_SCHEMA['properties']['segments']['items']['additionalProperties'])
        self.assertFalse(COMPACT_SEGMENT_SCHEMA['properties']['segments']['items']['additionalProperties'])

    def test_startup_warms_the_selected_bundled_voice_and_reuses_loaded_engine(self):
        bridge = self.bridge(tts_provider='kokoro', tts_voice='am_michael')
        engine = Mock()
        engine.get_voices.return_value = ['am_michael', 'bm_george']
        bridge.kokoro = engine
        bridge.prepare_speech()
        engine.create.assert_called_once_with('Ready.', voice='am_michael', speed=.95, lang='en-us')
        self.assertEqual(bridge.loaded_tts_voice, 'am_michael')
        self.assertIs(bridge.kokoro, engine)

    def test_missing_bundled_voice_fails_without_speaking_or_falling_back(self):
        bridge = self.bridge(tts_provider='kokoro', tts_voice='unknown')
        bridge.kokoro = Mock()
        bridge.kokoro.get_voices.return_value = ['am_michael']
        with self.assertRaisesRegex(ContractError, 'not in the bundled'):
            bridge.prepare_speech()
        bridge.kokoro.create.assert_not_called()
        self.assertIsNone(bridge.loaded_tts_voice)


if __name__ == '__main__':
    unittest.main()
