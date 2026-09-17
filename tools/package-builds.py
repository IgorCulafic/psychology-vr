"""Archive existing Windows players for a GitHub Release; does not rebuild Unity."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.cache/releases/v0.1.0-prototype'
BUILDS = [
    ('Windows', 'AlexPrototype.exe', 'psychology-vr-windows.zip'),
    ('CandidatePreview', 'JumperPreview.exe', 'psychology-vr-character-preview.zip'),
]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {'note': 'Existing development players; not rebuilt by this script.', 'archives': []}
    for folder, executable, archive_name in BUILDS:
        source = ROOT / 'unity/Builds' / folder
        if not (source / executable).is_file():
            raise FileNotFoundError(source / executable)
        files = sorted(p for p in source.rglob('*') if p.is_file()
                       and not any('BackUpThisFolder_ButDontShipItWithYourGame' in part for part in p.parts)
                       and p.suffix.lower() != '.log')
        archive = OUTPUT / archive_name
        rows = []
        print('Packaging ' + archive_name, flush=True)
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
            for path in files:
                relative = path.relative_to(ROOT).as_posix()
                bundle.write(path, relative)
                rows.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
        with zipfile.ZipFile(archive) as bundle:
            invalid = bundle.testzip()
            if invalid:
                raise ValueError('Archive CRC check failed: ' + invalid)
            expected = 'unity/Builds/' + folder + '/' + executable
            if expected not in bundle.namelist():
                raise ValueError('Missing player executable: ' + expected)
        manifest['archives'].append({'file': archive_name, 'sha256': sha256(archive),
                                     'bytes': archive.stat().st_size, 'files': rows})
        print('Verified ' + archive_name + ' (' + str(len(rows)) + ' files)', flush=True)
    manifest_path = OUTPUT / 'build-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    checksums = ['{}  {}'.format(row['sha256'], row['file']) for row in manifest['archives']]
    checksums.append(sha256(manifest_path) + '  ' + manifest_path.name)
    (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    print('Release assets: ' + str(OUTPUT), flush=True)


if __name__ == '__main__':
    main()
