import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from alex_service import Bridge
import model_selection


class ModelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        config=json.loads((model_selection.ROOT/'services/config.example.json').read_text())
        config.update(dialogue_provider='llama.cpp',dialogue_model='bonsai',higgs_quantization='bf16',session_log_dir=str(self.root/'logs'))
        self.bridge=Bridge(config,self.root/'config.json')
        self.models=self.bridge.models
        self.key=self.bridge.new_session()['session_id']

    def test_refuses_uninstalled_and_unknown_models(self):
        with self.assertRaisesRegex(ValueError,'not installed'):self.models.select('../evil.exe')
        with patch.object(Path,'is_file',return_value=False):
            with self.assertRaisesRegex(ValueError,'not installed'):self.models.select('gemma')

    def test_rejects_switch_during_generation_or_unacknowledged_playback(self):
        session=self.bridge.sessions[self.key]
        with patch.object(Path,'is_file',return_value=True):
            session.busy=True
            with self.assertRaisesRegex(ValueError,'Finish or stop'):self.models.select('gemma')
            session.busy=False;session.stream={'closed':False}
            with self.assertRaisesRegex(ValueError,'Finish or stop'):self.models.select('gemma')

    def test_switch_blocks_new_turns_and_duplicate_switches(self):
        with patch.object(Path,'is_file',return_value=True),patch.object(model_selection.threading,'Thread'):
            self.assertTrue(self.models.select('gemma')['switching'])
            with self.assertRaisesRegex(ValueError,'already in progress'):self.models.select('qwen')
            with self.assertRaisesRegex(ValueError,'loading'):self.bridge.start_stream(self.key,'Hello')
            with self.assertRaisesRegex(ValueError,'loading'):self.bridge.turn(self.key,'Hello')

    def test_success_preserves_history_and_voice_and_resets_context(self):
        session=self.bridge.sessions[self.key];session.history=[{'role':'user','content':'Earlier words'}]
        previous=json.dumps(session.history);self.bridge.context_limit=4096
        (self.root/'services/.runtime').mkdir(parents=True)
        with patch.object(model_selection,'ROOT',self.root),patch.object(model_selection.subprocess,'run',return_value=Mock(returncode=0)):
            self.models.switching=True;self.models._change('gemma')
        self.assertEqual(self.bridge.config['dialogue_model'],'gemma')
        self.assertEqual(self.bridge.config['higgs_quantization'],'bf16')
        self.assertEqual(json.dumps(session.history),previous)
        self.assertIsNone(self.bridge.context_limit)
        self.assertFalse(self.models.switching)

    def test_failed_switch_does_not_claim_requested_model(self):
        (self.root/'services/.runtime').mkdir(parents=True)
        with patch.object(model_selection,'ROOT',self.root),patch.object(model_selection.subprocess,'run',return_value=Mock(returncode=1)):
            self.models.switching=True;self.models._change('gemma')
        self.assertEqual(self.bridge.config['dialogue_model'],'bonsai')
        self.assertIn('failed',self.models.error)
        self.assertFalse(self.models.switching)

    def test_fixture_cannot_switch_models(self):
        bridge=Bridge(self.bridge.config)
        self.assertFalse(bridge.models.status()['enabled'])
        with self.assertRaisesRegex(ValueError,'unavailable'):bridge.models.select('gemma')


if __name__=='__main__':unittest.main()
