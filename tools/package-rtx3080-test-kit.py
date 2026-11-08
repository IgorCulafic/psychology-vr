"""Package the test kit plus required v0.5.3 service overlay, without models or local config."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('latency_overlay', ROOT/'tools/package-latency-update.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
EXTRA = ['Test RTX 3080.cmd', 'README-RTX3080-TEST.txt', 'tools/test-rtx3080.py',
         'tools/test-rtx3080.ps1', 'tools/package-rtx3080-test-kit.py',
         'services/config.rtx3080-test.example.json', 'services/test_rtx3080_test_kit.py',
         'services/inference_runtime.py', 'docs/RTX3080_TEST_GUIDE.md',
         'docs/benchmarks/2026-10-17-rtx3080-test-kit.json']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist/PsychologyVR-RTX3080-Test-Kit.zip')
    parser.add_argument('--source-commit', default='working-tree')
    args = parser.parse_args()
    names = list(dict.fromkeys([*overlay.FILES, *EXTRA]))
    names += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'voices/recorded').rglob('*')) if p.is_file()]
    manifest = dict(version='0.5.4', type='3080 test kit and v0.5.3 overlay; complete base application required',
        source_commit=args.source_commit, contains_weights=False, replaces_local_configuration=False,
        locally_tested_gpu='RTX 3080 10 GB', rtx3080_12gb_measured=False, audible_14s_verified=False, files=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name in names:
            if name.endswith('config.local.json') or '/.runtime/' in name or name.startswith('.cache/'):
                raise ValueError('Private/runtime file in package: ' + name)
            data = (ROOT/name).read_bytes()
            manifest['files'].append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            bundle.writestr('PsychologyVR/' + name, data)
        bundle.writestr('PsychologyVR/RTX3080-TEST-MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(args.output) as bundle:
        if bundle.testzip():
            raise ValueError('ZIP CRC verification failed')
        for row in manifest['files']:
            if hashlib.sha256(bundle.read('PsychologyVR/' + row['path'])).hexdigest() != row['sha256']:
                raise ValueError('ZIP file hash mismatch: ' + row['path'])
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix('.sha256').write_text(digest + '  ' + args.output.name + '\n', encoding='utf-8')
    args.output.with_suffix('.manifest.json').write_text(json.dumps(dict(manifest, zip_sha256=digest,
        zip_bytes=args.output.stat().st_size, zip_crc_verified=True), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(path=str(args.output), bytes=args.output.stat().st_size, sha256=digest)))


if __name__ == '__main__':
    main()
