"""Download the pinned official llama.cpp Windows CUDA runtime into .tools."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'b10909'
OUT = ROOT / '.tools/llama'
OUT.mkdir(parents=True, exist_ok=True)
with urllib.request.urlopen(f'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{TAG}') as response:
    release = json.load(response)
names = [f'llama-{TAG}-bin-win-cuda-13.3-x64.zip', 'cudart-llama-bin-win-cuda-13.3-x64.zip']
record = {'release': TAG, 'files': []}
for name in names:
    asset = next(a for a in release['assets'] if a['name'] == name)
    archive = OUT / name
    print('Downloading', name, flush=True)
    urllib.request.urlretrieve(asset['browser_download_url'], archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected = asset.get('digest')
    if expected and expected != 'sha256:' + digest:
        raise RuntimeError('Release digest mismatch')
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if not (OUT / info.filename).resolve().is_relative_to(OUT.resolve()):
                raise RuntimeError('Unexpected archive path')
        z.extractall(OUT)
    record['files'].append({'name': name, 'sha256': digest, 'url': asset['browser_download_url']})
(ROOT / 'docs/generated/llama-runtime.json').write_text(json.dumps(record, indent=2))
print('Runtime ready:', OUT, flush=True)
