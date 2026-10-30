import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import threading
from unittest.mock import patch, Mock
from copy import deepcopy

from alex_service import Bridge, ContractError, ROOT
from patient_relationship import initial_relationship, wants_fuller_reply
from latency_metrics import playback_schedule
from voice_cast import VoiceCast
from higgs_service import HiggsVoice

spec = importlib.util.spec_from_file_location('optimization_settings', ROOT/'tools/optimization-settings.py')
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class LatencyControlsTests(unittest.TestCase):
    def config(self):
        return dict(json.loads((ROOT/'services/config.example.json').read_text()),
                    dialogue_provider='llama.cpp', tts_provider='none')

    def test_ordinary_budget_rewrites_without_truncating_or_mutating_relationship(self):
        config = self.config()
        config.update(llm_ordinary_word_limit=16, llm_short_replies=True, llm_stable_prefix=True)
        bridge = Bridge(config)
        bridge.fit_context = lambda *a, **k: []
        profile = bridge.profiles['alex-earthquake']
        relationship = initial_relationship(profile)
        before = deepcopy(relationship)
        requests = []
        def model(url, body, timeout):
            requests.append(deepcopy(body))
            line = 'word ' * 20 if len(requests) == 1 else 'I need a little time to feel safe.'
            return {'choices':[{'message':{'content':json.dumps({'segments':[
                dict(text=line, emotion='anxious', intensity=.4)]})}}]}
        bridge.post_json = model
        reply = bridge.generate('How are you?', [], False, dict(relationship=relationship), profile)
        self.assertEqual(reply[0]['text'], 'I need a little time to feel safe.')
        self.assertEqual(len(requests), 2)
        self.assertIn('HARD MAXIMUM of 16 words', requests[1]['messages'][0]['content'])
        self.assertIn('"word_limit": 16', requests[0]['messages'][-1]['content'])
        self.assertEqual(relationship, before)

    def test_explicit_detail_keeps_its_budget(self):
        config = self.config()
        config.update(llm_ordinary_word_limit=16, llm_stable_prefix=True)
        bridge = Bridge(config)
        bridge.fit_context = lambda *a, **k: []
        profile = bridge.profiles['ivan-work-exhaustion']
        relationship = dict(initial_relationship(profile), invites_detail=True, word_limit=75, distress=40)
        self.assertTrue(wants_fuller_reply(relationship))
        line = ' '.join(['detail'] * 40)
        calls = []
        def model(url, body, timeout):
            calls.append(deepcopy(body))
            return {'choices':[{'message':{'content':json.dumps({'segments':[
                dict(text=line, emotion='neutral', intensity=.4)]})}}]}
        bridge.post_json = model
        self.assertEqual(bridge.generate('Explain', [], False, dict(relationship=relationship), profile)[0]['text'], line)
        self.assertEqual(len(calls), 1)
        self.assertIn('"word_limit": 75', calls[0]['messages'][-1]['content'])

    def test_batch_lip_sync_and_mtp_off_preserve_selected_model_and_language(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            root = Path(folder)
            (root/'services').mkdir()
            catalog = {'models':[{'id':'gemma','model_path':'qat.gguf'}]}
            (root/'services/dialogue-models.json').write_text(json.dumps(catalog))
            path = root/'services/config.local.json'
            original = dict(self.config(), dialogue_model='gemma', llm_model_path='qat.gguf',
                            llm_gpu_layers=99, higgs_quantization='bf16', conversation_language='cnr', llm_mtp=False)
            path.write_text(json.dumps(original))
            with patch.object(settings, 'ROOT', root):
                for profile in ('throughput','vr-friendly','mtp-off','audio-envelope','rhubarb'):
                    result = settings.update(path, profile)
                    for key in ('dialogue_model','llm_model_path','higgs_quantization','conversation_language'):
                        self.assertEqual(result[key], original[key])
                snapshot = path.read_bytes()
                with self.assertRaisesRegex(ValueError, 'selected model'):
                    settings.update(path, 'mtp-on')
                self.assertEqual(path.read_bytes(), snapshot)

    def test_latency_preset_uses_qat_with_bf16_and_quality_reverses_the_budget(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            root = Path(folder)
            (root/'services').mkdir()
            (root/'services/dialogue-models.json').write_text(json.dumps({'models':[
                {'id':'gemma','model_path':'qat.gguf'}, {'id':'gemma-q8','model_path':'q8.gguf'}]}))
            path = root/'services/config.local.json'
            path.write_text(json.dumps(self.config()))
            with patch.object(settings, 'ROOT', root):
                snapshot = path.read_bytes()
                with self.assertRaisesRegex(ValueError, 'not installed'):
                    settings.update(path, 'latency-bf16')
                self.assertEqual(path.read_bytes(), snapshot)
                (root/'qat.gguf').write_bytes(b'fixture')
                result = settings.update(path, 'latency-bf16')
                self.assertEqual((result['dialogue_model'],result['higgs_quantization'],result['conversation_language']),
                                 ('gemma','bf16','cnr'))
                self.assertFalse(result['higgs_allow_quantized_cast'])
                self.assertEqual(result['llm_ordinary_word_limit'],18)
                restored = settings.update(path, 'quality')
                self.assertEqual(restored['dialogue_model'],'gemma-q8')
                self.assertIsNone(restored['llm_ordinary_word_limit'])
                self.assertEqual(restored['stt_beam_size'],5)

    def test_later_generation_gap_excludes_planned_pauses_and_holds(self):
        segments=[dict(ready_ms=4000,audio_duration_seconds=2,pause_before_seconds=.2,hold_after_seconds=.3),
                  dict(ready_ms=8000,audio_duration_seconds=3,pause_before_seconds=.1,hold_after_seconds=0),
                  dict(ready_ms=9000,audio_duration_seconds=1)]
        rows=playback_schedule(segments)
        self.assertEqual([r['predicted_start_seconds'] for r in rows],[4.2,8.1,11.1])
        self.assertEqual([r['extra_preparation_wait_seconds'] for r in rows],[0.,1.5,0.])

    def test_sentence_override_preserves_cast_reference_and_never_edits_manifest(self):
        normal=VoiceCast(ROOT)
        fast=VoiceCast(ROOT,True)
        segment=dict(text='Prva rečenica. Druga rečenica.',emotion='angry',intensity=.6,
                     gesture='none',voice_style='normal',gaze='automatic',transition_seconds=.65,
                     pause_before_seconds=0.,hold_after_seconds=.2,gesture_at=0.,gesture_duration_seconds=2.5)
        for scenario in normal.scenarios:
            original=normal.resolve(scenario,segment)
            changed=fast.resolve(scenario,segment)
            self.assertEqual(changed,dict(original,mode='sentences'))
            self.assertEqual(len(fast.delivery_segments(scenario,[segment])),2)
            self.assertEqual(normal.resolve(scenario,segment),original)
        with self.assertRaises(ValueError):VoiceCast(ROOT,'false')

    def test_failed_benchmark_writes_report_without_claiming_success(self):
        spec=importlib.util.spec_from_file_location('response_benchmark',ROOT/'tools/benchmark-response.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        config=self.config()
        config.update(dialogue_provider='scripted',stt_warmup=False,tts_warmup=False)
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            report=module.benchmark(config,Path(folder),turns=4)
            # tts_provider=none cannot pass a speech latency test.
            self.assertFalse(report['preparation_target_met'])
            self.assertFalse(report['end_to_end_target_verified'])
            self.assertIn('error',report['samples'][0])
            self.assertEqual(json.loads((Path(folder)/'report.json').read_text())['target_seconds'],14)

    def test_gpu_cleanup_failure_cannot_leave_speech_worker_locked(self):
        voice=HiggsVoice.__new__(HiggsVoice)
        voice.config={'higgs_release_unused_vram':True}
        voice.lock=threading.Lock()
        voice.torch=Mock()
        voice.torch.cuda.empty_cache.side_effect=RuntimeError('CUDA cleanup failed')
        voice.prepared_openings={('test','neutral','A line.'):b'prepared'}
        with self.assertRaisesRegex(RuntimeError,'CUDA cleanup'):
            voice.synthesize(dict(text='A line.',emotion='neutral'),'test')
        self.assertFalse(voice.lock.locked())


if __name__ == '__main__':
    unittest.main()
