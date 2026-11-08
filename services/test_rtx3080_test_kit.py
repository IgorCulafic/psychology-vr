"""Protect configuration, ownership boundaries and benchmark interpretation."""
import argparse
from copy import deepcopy
import importlib.util
import io
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('test_kit_3080', ROOT/'tools/test-rtx3080.py')
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class Test3080Kit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'services/.runtime').mkdir(exist_ok=True)

    def test_scoped_profiles_preserve_template_and_require_explicit_precision_change(self):
        base = kit.read(ROOT/'services/config.rtx3080-test.example.json')
        base.update(llm_url='http://other-server/v1/chat/completions',
                    appraisal_llm_url='http://another-server', stt_device='cuda')
        original = deepcopy(base)
        ordinary = kit.stage_config(base, 'voice', 'bf16', 10240)
        experimental = kit.stage_config(base, 'combined', 'nf4-experiment', 10240)
        twelve = kit.stage_config(base, 'combined', 'nf4-experiment', 12288)
        self.assertEqual(base, original)
        self.assertEqual(ordinary['higgs_quantization'], 'bf16')
        self.assertFalse(ordinary['higgs_allow_quantized_cast'])
        self.assertFalse(ordinary['speech_cache_enabled'])
        self.assertEqual(experimental['higgs_quantization'], 'nf4')
        self.assertTrue(experimental['higgs_allow_quantized_cast'])
        self.assertEqual((experimental['llm_gpu_layers'], twelve['llm_gpu_layers']), (16, 24))
        self.assertEqual(ordinary['conversation_language'], 'cnr')
        self.assertEqual(ordinary['llm_url'], 'http://127.0.0.1:8087/v1/chat/completions')
        self.assertEqual(ordinary['stt_device'], 'cpu')
        self.assertNotIn('appraisal_llm_url', ordinary)
        self.assertEqual(kit.stage_config(base, 'combined', 'bf16-cpu-dialogue', 10240)['llm_gpu_layers'], 0)

    def test_existing_listener_is_refused_and_remains_alive(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with patch.object(kit, 'PORTS', (listener.getsockname()[1],)):
                with self.assertRaisesRegex(RuntimeError, 'No existing process was stopped'):
                    kit.require_idle()
                self.assertEqual(kit.occupied_ports(), [listener.getsockname()[1]])

    def test_both_owned_service_health_contracts_are_recognized(self):
        for port, response in ((8087, b'{"status":"ok"}'), (8766, b'{"ok":true,"provider":"higgs"}')):
            process = Mock()
            process.poll.return_value = None
            with self.subTest(port=port), patch.object(kit.urllib.request, 'urlopen', return_value=io.BytesIO(response)):
                self.assertGreaterEqual(kit.wait_health(process, port, 1), 0)

    def test_owned_process_stops_when_stage_raises(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            with self.assertRaisesRegex(ValueError, 'injected failure'):
                with kit.owned([sys.executable, '-c', 'import time; time.sleep(120)'], Path(folder)/'worker.log') as process:
                    raise ValueError('injected failure')
            self.assertIsNotNone(process.poll())

    def test_blocked_run_keeps_config_and_writes_honest_partial_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            root = Path(folder)
            (root/'services').mkdir()
            local = root/'services/config.local.json'
            original = b'{"personal_setting": "keep this"}\n'
            local.write_bytes(original)
            args = argparse.Namespace(mode='quick', output=root/'results', allow_quantized_voice=False)
            with patch.object(kit, 'ROOT', root), patch.object(kit, 'hardware', return_value={'gpu':{'available':False}}), \
                 patch.object(kit, 'windows_memory', return_value={'available':False}), \
                 patch.object(kit, 'require_idle', side_effect=RuntimeError('Existing service')), \
                 patch.object(kit, 'occupied_ports', return_value=[8087]):
                self.assertEqual(kit.main(args), 2)
            report = kit.read(root/'results/report.json')
            self.assertEqual(report['status'], 'blocked')
            self.assertFalse(report['end_to_end_target_verified'])
            self.assertTrue(report['config_local_unchanged'])
            self.assertEqual(local.read_bytes(), original)
            self.assertTrue((root/'results/REPORT.txt').is_file())

    def test_nf4_cli_requires_opt_in_before_creating_any_output(self):
        with self.assertRaisesRegex(ValueError, '--allow-quantized-voice'):
            kit.main(argparse.Namespace(mode='combined-nf4', allow_quantized_voice=False))

    def test_incomplete_worker_report_survives_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            path = Path(folder)/'report.json'
            kit.save(path, {'samples':[{'seconds':3.2}], 'completed':False})
            with self.assertRaises(RuntimeError):
                class Finished:
                    returncode = 1
                    def poll(self): return 1
                kit.wait_worker(Finished(), 1)
            self.assertEqual(kit.read(path)['samples'][0]['seconds'], 3.2)

    def test_failed_stage_exposes_partial_timings_in_main_report(self):
        template = ROOT/'services/config.rtx3080-test.example.json'
        class QuietTelemetry:
            def __init__(self, output): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def fail_with_partial(config, stage, output, args):
            kit.save(output/'report.json', dict(median_seconds=31.955, completed=False,
                preparation_target_met=False, samples=[{'error':'Injected failure'}]))
            raise RuntimeError('Injected failure')
        info = dict(available=True, values={'name':'RTX 3080', 'memory.total':10240, 'memory.used':300})
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as folder:
            root = Path(folder)
            args = argparse.Namespace(mode='combined-bf16', gpu_layers=None, config=template,
                                      output=root/'results', allow_quantized_voice=False)
            with patch.object(kit, 'ROOT', root), patch.object(kit, 'hardware', return_value={'gpu':info}), \
                 patch.object(kit, 'windows_memory', return_value={'available':False}), \
                 patch.object(kit, 'require_idle'), patch.object(kit, 'occupied_ports', return_value=[]), \
                 patch.object(kit, 'gpu_sample', return_value=info), patch.object(kit, 'missing_assets', return_value=[]), \
                 patch.object(kit, 'Telemetry', QuietTelemetry), patch.object(kit, 'execute_stage', side_effect=fail_with_partial):
                self.assertEqual(kit.main(args), 2)
            report = kit.read(root/'results/report.json')
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['stages'][0]['result']['median_seconds'], 31.955)
            self.assertFalse(report['stages'][0]['result']['preparation_target_met'])
            self.assertIn('31.955s', (root/'results/REPORT.txt').read_text())


if __name__ == '__main__':
    unittest.main()
