import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hardware_profiles import profiles, setup


ROOT = Path(__file__).resolve().parents[1]


class ProfileInstallationTests(unittest.TestCase):
    def test_real_installer_downloads_missing_files_when_switching_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'services').mkdir()
            (root / 'tools').mkdir()
            shutil.copy2(ROOT / 'tools/setup-portable.py', root / 'tools/setup-portable.py')
            for name in ('config.rtx3080.json', 'config.rtx4090.json', 'dialogue-models.json'):
                shutil.copy2(ROOT / 'services' / name, root / 'services' / name)
            (root / 'voices').mkdir()
            (root / 'voices/reference.wav').write_bytes(b'reference')
            (root / 'voices/reference.json').write_text('{"text":"reference"}')
            game = root / 'unity/Builds/Windows/AlexPrototype.exe'
            game.parent.mkdir(parents=True)
            game.touch()

            manifest = json.loads((ROOT / 'services/portable-manifest.json').read_text())
            content = b'test model'
            for group in ('models', 'dialogue_variants', 'auxiliary_models'):
                for model in manifest.get(group, []):
                    for entry in model['files']:
                        entry.pop('url', None)
                        entry.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
            for runtime in [*manifest['runtimes'], *manifest.get('bonsai_runtimes', []),
                            *(r for group in manifest.get('runtime_profiles', {}).values() for r in group)]:
                for name in [runtime['executable'], *runtime.get('required', [])]:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            (root / 'services/portable-manifest.json').write_text(json.dumps(manifest))

            downloaded = []
            def run(command, **kwargs):
                if 'download' in command:
                    destination = Path(command[command.index('--local-dir') + 1])
                    names = command[3:command.index('--revision')]
                    for name in names:
                        path = destination / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(content)
                        downloaded.append(path.relative_to(root).as_posix())
                return SimpleNamespace(returncode=0)

            cuda = SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: True,
                                   get_device_properties=lambda _: SimpleNamespace(name='RTX 4090', total_memory=24*1024**3))
            modules = {'torch': SimpleNamespace(cuda=cuda), 'faster_whisper': SimpleNamespace(),
                       'kokoro_onnx': SimpleNamespace(), 'torchaudio': SimpleNamespace(),
                       'transformers': SimpleNamespace(), 'soundfile': SimpleNamespace(info=lambda _: SimpleNamespace(duration=4))}
            def invoke(*args):
                with patch.object(sys, 'argv', ['setup-portable.py', *args]):
                    setup.main()

            # Exercise the installer's real CLI exit codes in a separate process.
            def cli_check(gpu_available=True, missing_kokoro=False, missing_torch=False):
                script = '''
import runpy, subprocess, sys, types
S=types.SimpleNamespace
subprocess.run=lambda *args, **kwargs: S(returncode=0)
cuda=S(is_available=lambda: GPU_AVAILABLE, is_bf16_supported=lambda: True,
       get_device_properties=lambda _: S(name="RTX 4090", total_memory=24*1024**3))
sys.modules.update({"torch":S(cuda=cuda), "faster_whisper":S(), "kokoro_onnx":S(),
                    "torchaudio":S(), "transformers":S(), "soundfile":S(info=lambda _: S(duration=4))})
if MISSING_KOKORO: sys.modules["kokoro_onnx"] = None
if MISSING_TORCH: sys.modules["torch"] = None
sys.argv=[sys.argv[1], "--check"]
runpy.run_path(sys.argv[0], run_name="__main__")
'''.replace('GPU_AVAILABLE', repr(gpu_available)).replace('MISSING_KOKORO', repr(missing_kokoro)).replace('MISSING_TORCH', repr(missing_torch))
                return real_run([sys.executable, '-B', '-c', script, str(root / 'tools/setup-portable.py')],
                                cwd=root, capture_output=True, text=True)

            real_run = subprocess.run
            with patch.object(setup, 'ROOT', root), patch.dict(sys.modules, modules), patch.object(setup.subprocess, 'run', side_effect=run):
                profiles.select_profile('rtx4090', root)
                missing = cli_check()
                self.assertEqual(missing.returncode, 2, missing.stdout + missing.stderr)
                self.assertIn('Missing or incomplete model', missing.stderr)
                invalid_gpu = cli_check(False)
                self.assertEqual(invalid_gpu.returncode, 1)
                self.assertIn('NVIDIA GPU', invalid_gpu.stderr)
                local = root / 'services/config.local.json'
                original = local.read_bytes()
                local.write_text('{invalid')
                invalid_config = cli_check()
                self.assertEqual(invalid_config.returncode, 1)
                self.assertIn('not valid JSON', invalid_config.stderr)
                local.write_bytes(original)
                invoke()
                invoke('--check')
                no_kokoro = cli_check(missing_kokoro=True)
                self.assertEqual(no_kokoro.returncode, 0, no_kokoro.stdout + no_kokoro.stderr)
                saved = local.read_bytes()
                preset_config = json.loads(saved)
                preset_config['hardware_preset'] = 'rtx4090'
                local.write_text(json.dumps(preset_config))
                missing_torch = cli_check(missing_torch=True)
                self.assertEqual(missing_torch.returncode, 3, missing_torch.stdout + missing_torch.stderr)
                local.write_bytes(saved)
                self.assertFalse((root / '.cache/kokoro/kokoro-v1.0.onnx').exists())
                profiles.select_profile('rtx3080', root)
                missing_dependency = cli_check(missing_kokoro=True)
                self.assertEqual(missing_dependency.returncode, 3, missing_dependency.stdout + missing_dependency.stderr)
                self.assertIn('kokoro_onnx', missing_dependency.stderr)
                with self.assertRaisesRegex(RuntimeError, 'Missing or incomplete model'):
                    invoke('--check')
                invoke()
                invoke('--check')
                self.assertIn('.cache/kokoro/kokoro-v1.0.onnx', downloaded)
                self.assertIn('.cache/kokoro/voices-v1.0.bin', downloaded)
                before = list(downloaded)
                profiles.select_profile('rtx4090', root)
                invoke('--check')
                invoke()
                self.assertEqual(downloaded, before)


if __name__ == '__main__':
    unittest.main()
