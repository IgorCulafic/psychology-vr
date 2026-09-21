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
        for model in manifest['models']:
            self.assertRegex(model['revision'],r'^[a-f0-9]{40}$')
            for entry in model['files']:
                self.assertRegex(entry['sha256'],r'^[a-f0-9]{64}$')
                self.assertGreater(entry['bytes'],0)
                setup.contained(ROOT,model['destination']+'/'+entry['name'])
        for runtime in manifest['runtimes']:
            self.assertRegex(runtime['sha256'],r'^[a-f0-9]{64}$')
            self.assertTrue(runtime['url'].startswith('https://github.com/'))


if __name__=='__main__':unittest.main()
