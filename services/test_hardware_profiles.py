import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


profiles=load_module('hardware_profiles',ROOT/'tools/hardware-profile.py')
setup=load_module('profile_portable_setup',ROOT/'tools/setup-portable.py')


class HardwareProfileTests(unittest.TestCase):
    def fixture(self):
        folder=tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime')
        self.addCleanup(folder.cleanup)
        root=Path(folder.name);(root/'services').mkdir()
        for name in ('config.rtx3080.json','config.rtx4090.json','dialogue-models.json'):
            shutil.copy2(ROOT/'services'/name,root/'services'/name)
        return root

    def test_both_profiles_enable_only_the_approved_speed_choices(self):
        for name in profiles.PROFILES:
            config=profiles.profile_config(name)
            for key in ('llm_cache_slots','llm_stable_prefix','llm_compact_delivery','tts_warmup',
                        'stt_warmup','speech_cache_enabled','recorded_speech_enabled'):
                self.assertIs(config[key],True,(name,key))
            for key in ('higgs_fast_decode','llm_short_replies','higgs_sentence_streaming','llm_mtp','higgs_allow_quantized_cast'):
                self.assertIs(config[key],False,(name,key))
            self.assertIsNone(config['llm_ordinary_word_limit'])
            self.assertEqual(config['stt_beam_size'],5)
            self.assertEqual(config['lip_sync_provider'],'rhubarb')
            self.assertEqual(config['higgs_quantization'],'bf16')
        local=profiles.profile_config('rtx3080');remote=profiles.profile_config('rtx4090')
        self.assertEqual((local['tts_provider'],local['conversation_language'],local['llm_gpu_layers'],local['llm_batch_size'],local['llm_ubatch_size']),('kokoro','en',40,64,32))
        self.assertEqual((remote['tts_provider'],remote['conversation_language'],remote['llm_gpu_layers']),('higgs','cnr',32))

    def test_switch_roundtrip_backs_up_exact_previous_settings(self):
        root=self.fixture();path=root/'services/config.local.json'
        original=b'\xef\xbb\xbf{"custom_setting":true}'
        path.write_bytes(original)
        templates={name:(root/f'services/config.{name}.json').read_bytes() for name in profiles.PROFILES}
        # Windows clock resolution must not let rapid switches overwrite backups.
        with patch.object(profiles.time,'time_ns',return_value=123):
            profiles.select_profile('rtx3080',root)
            first=path.read_bytes()
            profiles.select_profile('rtx4090',root)
            second=path.read_bytes()
            profiles.select_profile('rtx3080',root)
        self.assertEqual(path.read_bytes(),first)
        backups=[p.read_bytes() for p in (root/'services/.runtime/config-backups').glob('*.json')]
        self.assertCountEqual(backups,[original,first,second])
        self.assertEqual(templates,{name:(root/f'services/config.{name}.json').read_bytes() for name in profiles.PROFILES})
        with self.assertRaises(ValueError):profiles.select_profile('../private',root)
        self.assertEqual(path.read_bytes(),first)

    def test_setup_preserves_3080_config_without_requiring_higgs_reference(self):
        root=self.fixture();config=profiles.select_profile('rtx3080',root)
        path=root/'services/config.local.json';before=path.read_bytes()
        with patch.object(setup,'ROOT',root),patch.object(setup,'gpu_properties',side_effect=AssertionError('No legacy GPU migration')):
            result=setup.configure()
        self.assertEqual(result,config)
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse((root/'voices').exists())

    def test_fresh_setup_chooses_3080_default(self):
        root=self.fixture()
        self.assertFalse((root/'services/config.local.json').exists())
        with patch.object(setup,'ROOT',root):
            config=setup.configure()
        self.assertEqual(config['hardware_profile'],'rtx3080')
        self.assertEqual(config['tts_provider'],'kokoro')
        self.assertEqual(config['conversation_language'],'en')
        self.assertEqual((config['llm_gpu_layers'],config['llm_batch_size'],config['llm_ubatch_size']),(40,64,32))

    def test_selected_downloads_match_provider_and_exclude_optional_draft(self):
        manifest=json.loads((ROOT/'services/portable-manifest.json').read_text())
        local=setup.selected_manifest(manifest,profiles.profile_config('rtx3080'))
        self.assertEqual({m['destination'] for m in local['models']},{'.cache/models/gemma4-12b-qat','.cache/kokoro','.cache/whisper/small.en'})
        self.assertTrue(any(r['executable'].endswith('cudart64_12.dll') for r in local['runtimes']))
        self.assertFalse(any(r['executable'].endswith('cudart64_13.dll') for r in local['runtimes']))
        remote=setup.selected_manifest(manifest,profiles.profile_config('rtx4090'))
        self.assertEqual(len(remote['models']),4)
        self.assertEqual([f['name'] for f in remote['models'][0]['files']],['gemma-4-12B-it-Q8_0.gguf'])
        self.assertFalse(any(m['destination']=='.cache/kokoro' for m in remote['models']))

    def test_doctor_accepts_3080_without_importing_bf16_libraries(self):
        root=self.fixture();profiles.select_profile('rtx3080',root)
        game=root/'unity/Builds/Windows/AlexPrototype.exe';game.parent.mkdir(parents=True);game.touch()
        voice=root/'.cache/kokoro';voice.mkdir(parents=True)
        for name in ('kokoro-v1.0.onnx','voices-v1.0.bin'):(voice/name).touch()
        cuda=SimpleNamespace(is_available=lambda:True,get_device_properties=lambda _:SimpleNamespace(name='RTX 3080',total_memory=10*1024**3),
                             is_bf16_supported=lambda:(_ for _ in ()).throw(AssertionError('BF16 check should be skipped')))
        with patch.object(setup,'ROOT',root),patch.dict(sys.modules,{'torch':SimpleNamespace(cuda=cuda),
                'kokoro_onnx':SimpleNamespace(),'faster_whisper':SimpleNamespace(),
                'torchaudio':None,'transformers':None,'soundfile':None}):
            setup.doctor(False)

    def test_doctor_still_rejects_4090_bf16_profile_on_10gb_card(self):
        root=self.fixture();profiles.select_profile('rtx4090',root)
        cuda=SimpleNamespace(is_available=lambda:True,is_bf16_supported=lambda:True,
                             get_device_properties=lambda _:SimpleNamespace(name='RTX 3080',total_memory=10*1024**3))
        with patch.object(setup,'ROOT',root),patch.dict(sys.modules,{'torch':SimpleNamespace(cuda=cuda),
                'faster_whisper':SimpleNamespace(),'torchaudio':SimpleNamespace(),'transformers':SimpleNamespace(),
                'soundfile':SimpleNamespace(info=lambda _:SimpleNamespace(duration=4))}):
            with self.assertRaisesRegex(RuntimeError,'24 GB VRAM'):
                setup.doctor(False)


if __name__=='__main__':unittest.main()
