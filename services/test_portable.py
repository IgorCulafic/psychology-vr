import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portable_setup',ROOT/'tools/setup-portable.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class PortableTests(unittest.TestCase):
    def test_auto_selects_by_device_memory_not_combined_gpu_capacity(self):
        self.assertEqual(setup.resolve_preset('auto',24*1024**3),'rtx4090')
        self.assertEqual(setup.resolve_preset('auto',int(23.7*1024**3)),'rtx4090')
        self.assertEqual(setup.resolve_preset('auto',32*1024**3),'quality')
        with self.assertRaisesRegex(RuntimeError,'single NVIDIA GPU'):setup.resolve_preset('auto',16*1024**3)
        with self.assertRaisesRegex(RuntimeError,'Unknown'):setup.resolve_preset('typo',24*1024**3)

    def test_manual_presets_override_auto_detection(self):
        self.assertEqual(setup.resolve_preset('rtx4090',32*1024**3),'rtx4090')
        self.assertEqual(setup.resolve_preset('quality',24*1024**3),'quality')

    def test_only_selected_dialogue_quant_is_required(self):
        manifest=json.loads((ROOT/'services/portable-manifest.json').read_text())
        snapshot=json.dumps(manifest)
        for preset in ['quality','rtx4090']:
            chosen=setup.selected_manifest(manifest,setup.HARDWARE_PRESETS[preset])
            quant=[f['name'] for f in chosen['models'][0]['files'] if f['name'].endswith('.gguf')]
            self.assertEqual(quant,[Path(setup.HARDWARE_PRESETS[preset]['llm_model_path']).name])
            self.assertEqual(chosen['models'][1:],manifest['models'][1:])
        self.assertEqual(json.dumps(manifest),snapshot)
        with self.assertRaisesRegex(RuntimeError,'not in the download manifest'):
            setup.selected_manifest(manifest,{'llm_model_path':'unknown.gguf'})

    def test_auto_migration_keeps_voice_language_and_conversation_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir();(root/'voices').mkdir()
            (root/'services/config.expressive.example.json').write_text('{"hardware_preset":"auto"}')
            (root/'voices/reference.wav').write_bytes(b'audio')
            (root/'voices/reference.json').write_text('{"text":"Reference words."}')
            path=root/'services/config.local.json'
            path.write_text(json.dumps({'higgs_quantization':'bf16','higgs_temperature':.7,'conversation_language':'cnr','llm_gpu_layers':48}))
            with patch.object(setup,'ROOT',root),patch.object(setup,'gpu_properties',return_value=('RTX 4090',24*1024**3)):
                config=setup.configure()
                self.assertEqual(config['hardware_preset'],'auto')
                self.assertEqual(config['hardware_preset_resolved'],'rtx4090')
                self.assertEqual(config['llm_gpu_layers'],32)
                self.assertEqual(config['higgs_quantization'],'bf16')
                self.assertEqual(config['higgs_temperature'],.7)
                self.assertEqual(config['conversation_language'],'cnr')
                config=setup.configure('quality')
                self.assertEqual(config['llm_gpu_layers'],48)
                self.assertEqual(config['hardware_preset'],'quality')
                self.assertTrue(config['llm_model_path'].endswith('IQ4_XS.gguf'))

    def test_partial_config_gets_missing_defaults_and_exact_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir();(root/'voices').mkdir()
            (root/'services/config.expressive.example.json').write_text(json.dumps({'higgs_reference':'missing','higgs_temperature':.7,'tts_provider':'higgs'}))
            (root/'voices/reference.wav').write_bytes(b'audio')
            (root/'voices/reference.json').write_text('{"text":"Reference words."}')
            path=root/'services/config.local.json'
            original=b'\xef\xbb\xbf{"higgs_temperature":0.6,"conversation_language":"en","custom_setting":true}'
            path.write_bytes(original)
            with patch.object(setup,'ROOT',root):
                setup.configure()
                config=json.loads(path.read_text())
                self.assertEqual(config['higgs_reference'],'voices/reference.wav')
                self.assertEqual(config['higgs_python'],'.tools/portable-env/Scripts/python.exe')
                self.assertEqual(config['bridge_python'],config['higgs_python'])
                self.assertEqual(config['tts_provider'],'higgs')
                self.assertEqual(config['higgs_temperature'],.6)
                self.assertEqual(config['conversation_language'],'en')
                self.assertTrue(config['custom_setting'])
                backups=list((root/'services/.runtime/config-backups').glob('*.json'))
                self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),original)
                saved=path.read_bytes();setup.configure()
                self.assertEqual(path.read_bytes(),saved)
                self.assertEqual(len(list(backups[0].parent.glob('*.json'))),1)

    def test_custom_voice_and_providers_survive_config_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir();(root/'custom').mkdir()
            (root/'services/config.expressive.example.json').write_text('{"tts_provider":"higgs"}')
            (root/'custom/voice.wav').write_bytes(b'audio')
            (root/'custom/voice.json').write_text('{"text":"Custom voice."}')
            path=root/'services/config.local.json'
            path.write_text(json.dumps({'higgs_reference':'custom/voice.wav','tts_provider':'windows','higgs_python':'custom/python.exe'}))
            with patch.object(setup,'ROOT',root):setup.configure()
            config=json.loads(path.read_text())
            self.assertEqual(config['higgs_reference'],'custom/voice.wav')
            self.assertEqual(config['higgs_python'],'custom/python.exe')
            self.assertEqual(config['tts_provider'],'windows')

    def test_missing_voice_has_actionable_error_without_modifying_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir()
            (root/'services/config.expressive.example.json').write_text('{}')
            path=root/'services/config.local.json';path.write_text('{}')
            with patch.object(setup,'ROOT',root):
                with self.assertRaisesRegex(RuntimeError,'Voice reference missing'):setup.configure()
            self.assertEqual(path.read_text(),'{}')

    def test_invalid_config_has_actionable_error_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir()
            (root/'services/config.expressive.example.json').write_text('{}')
            path=root/'services/config.local.json'
            for value in ['{broken','[]','null']:
                path.write_text(value)
                with patch.object(setup,'ROOT',root):
                    with self.assertRaisesRegex(RuntimeError,'Setup.cmd'):setup.configure()
                self.assertEqual(path.read_text(),value)

    def test_archive_cannot_write_outside_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as bundle:bundle.writestr('../outside.txt','bad')
            with self.assertRaises(ValueError):setup.extract(archive,root/'extract')
            self.assertFalse((root/'outside.txt').exists())

    def test_config_uses_portable_runtime_and_does_not_overwrite_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'services').mkdir();(root/'voices').mkdir()
            (root/'services/config.expressive.example.json').write_text(json.dumps({'higgs_reference':'missing','higgs_temperature':.7}))
            with wave.open(str(root/'voices/reference.wav'),'wb') as audio:
                audio.setparams((1,2,16000,0,'NONE','not compressed'));audio.writeframes(bytes(16000*2*4))
            (root/'voices/reference.json').write_text('{"text":"This is a reference."}')
            with patch.object(setup,'ROOT',root):
                setup.configure()
                path=root/'services/config.local.json';config=json.loads(path.read_text())
                self.assertEqual(config['bridge_python'],'.tools/portable-env/Scripts/python.exe')
                config['higgs_temperature']=.6;path.write_text(json.dumps(config))
                setup.configure();self.assertEqual(json.loads(path.read_text())['higgs_temperature'],.6)

    def test_manifest_pins_models_and_keeps_downloads_within_root(self):
        manifest=json.loads((ROOT/'services/portable-manifest.json').read_text())
        self.assertEqual(len(manifest['models']),4)
        for model in [*manifest['models'],*manifest.get('dialogue_variants',[])]:
            self.assertRegex(model['revision'],r'^[a-f0-9]{40}$')
            for entry in model['files']:
                self.assertRegex(entry['sha256'],r'^[a-f0-9]{64}$')
                self.assertGreater(entry['bytes'],0)
                setup.contained(ROOT,model['destination']+'/'+entry['name'])
        for runtime in manifest['runtimes']:
            self.assertRegex(runtime['sha256'],r'^[a-f0-9]{64}$')
            self.assertTrue(runtime['url'].startswith('https://github.com/'))


if __name__=='__main__':unittest.main()
