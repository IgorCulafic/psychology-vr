import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from test_hardware_profiles import profiles

CSC = Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe')


@unittest.skipUnless(CSC.is_file(), 'Windows .NET compiler required')
class PortableLauncherTests(unittest.TestCase):
    def test_switching_profiles_prepares_missing_models_even_with_ready_stamp(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('tools', 'services/.runtime', '.tools/bootstrap', '.tools/portable-env/Scripts'):
                (root / directory).mkdir(parents=True)
            shutil.copy2(ROOT / 'tools/run-portable.ps1', root / 'tools/run-portable.ps1')
            for profile in ('rtx3080', 'rtx4090'):
                shutil.copy2(ROOT / f'services/config.{profile}.json', root / f'services/config.{profile}.json')
            (root / 'tools/launch.ps1').write_text("param([switch]$Desktop)\nAdd-Content -Path launched.txt -Value 'yes'\n")
            fake_source = root / 'fake.cs'
            fake_source.write_text('''
using System;
using System.IO;
class Fake {
    static int Main(string[] args) {
        if (Path.GetFileName(Environment.GetCommandLineArgs()[0]).Equals("uv.exe", StringComparison.OrdinalIgnoreCase)) {
            if (args.Length > 1 && args[0] == "python" && args[1] == "find") Console.WriteLine("fake-python");
            return 0;
        }
        string profile = File.ReadAllText("services/config.local.json");
        bool check = Array.IndexOf(args, "--check") >= 0;
        if (check && File.Exists("fail-check")) { Console.Error.WriteLine("Invalid configuration"); return 1; }
        if (check) return File.Exists("available.json") && File.ReadAllText("available.json") == profile ? 0 : 2;
        if (File.Exists("fail-setup")) return 1;
        File.WriteAllText("available.json", profile);
        File.AppendAllText("setups.txt", "setup\\n");
        return 0;
    }
}
''')
            fake_exe = root / 'fake.exe'
            subprocess.run([str(CSC), '/nologo', f'/out:{fake_exe}', str(fake_source)], check=True, capture_output=True)
            shutil.copy2(fake_exe, root / '.tools/portable-env/Scripts/python.exe')
            uv_zip = root / '.tools/bootstrap/uv.zip'
            with zipfile.ZipFile(uv_zip, 'w') as archive:
                archive.write(fake_exe, 'uv.exe')
            digest = hashlib.sha256(uv_zip.read_bytes()).hexdigest().upper()
            manifest = root / 'services/portable-manifest.json'
            manifest.write_text(json.dumps({'uv': {'sha256': digest, 'url': 'unused'}, 'python': '3.12'}))
            requirements = root / 'services/requirements-portable.txt'
            requirements.write_text('fixture')
            key = hashlib.sha256(manifest.read_bytes()).hexdigest().upper() + hashlib.sha256(requirements.read_bytes()).hexdigest().upper()
            stamp = json.dumps({'root': str(root), 'key': key})
            (root / 'services/.runtime/portable-ready.json').write_text(stamp)
            (root / 'services/.runtime/portable-environment.json').write_text(stamp)
            profiles.select_profile('rtx3080', root)
            (root / 'available.json').write_text((root / 'services/config.local.json').read_text())

            def start():
                env = dict(os.environ, PSModulePath='')
                return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                       str(root / 'tools/run-portable.ps1'), '-Mode', 'Desktop'],
                                      cwd=root, env=env, capture_output=True, text=True, timeout=30)

            profiles.select_profile('rtx4090', root)
            first = start()
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual((root / 'setups.txt').read_text().splitlines(), ['setup'])
            self.assertTrue((root / 'launched.txt').exists())
            self.assertEqual(start().returncode, 0)
            self.assertEqual((root / 'setups.txt').read_text().splitlines(), ['setup'])

            profiles.select_profile('rtx3080', root)
            second = start()
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual((root / 'setups.txt').read_text().splitlines(), ['setup', 'setup'])
            profiles.select_profile('rtx4090', root)
            (root / 'fail-setup').touch()
            failed = start()
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(len((root / 'launched.txt').read_text().splitlines()), 3)
            (root / 'fail-setup').unlink()
            (root / 'fail-check').touch()
            failed = start()
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('Invalid configuration', failed.stdout + failed.stderr)
            self.assertEqual((root / 'setups.txt').read_text().splitlines(), ['setup', 'setup'])


if __name__ == '__main__':
    unittest.main()
