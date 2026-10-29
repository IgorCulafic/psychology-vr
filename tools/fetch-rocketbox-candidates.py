"""Fetch four adult male facial-rig candidates, preserving source paths and license.

Run from the repository with Python. Uses a pinned upstream revision and verifies
each download against its Git blob SHA before writing the acquisition manifest.
Candidates are deliberately kept outside the production Unity Assets tree.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '0943055db6ec570bcef9f2c8b41c9e5467c808f9'
CACHE = ROOT / '.cache/character-research/rocketbox-tree.json'
if CACHE.exists():
    TREE = json.loads(CACHE.read_text(encoding='utf-8-sig'))
else:
    request = urllib.request.Request(
        f'https://api.github.com/repos/microsoft/Microsoft-Rocketbox/git/trees/{REVISION}?recursive=1',
        headers={'User-Agent': 'PsychologyVR-asset-fetcher'})
    with urllib.request.urlopen(request, timeout=60) as response:
        TREE = json.load(response)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(TREE), encoding='utf-8')
if TREE['sha'] != REVISION or TREE.get('truncated'):
    raise ValueError('Expected a complete inventory at the pinned revision')
OUT = ROOT / 'Assets/CharacterCandidates/Microsoft-Rocketbox'
NAMES = [f'Male_Adult_{number:02}' for number in range(1, 5)]
PREFIXES = [f'Assets/Avatars/Adults/{name}/' for name in NAMES]

def blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def fetch(item):
    relative = item['path']
    path = OUT / relative
    url = f'https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/{REVISION}/' + urllib.parse.quote(relative)
    data = path.read_bytes() if path.exists() else b''
    if blob_sha(data) != item['sha']:
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if blob_sha(data) != item['sha']:
            raise ValueError(f'Upstream hash mismatch: {relative}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f'Verified {relative}', flush=True)
    return {'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'git_blob_sha': item['sha'], 'url': url}

if __name__ == '__main__':
    wanted = [item for item in TREE['tree'] if item['type'] == 'blob' and
              (any(item['path'].startswith(prefix) for prefix in PREFIXES) or
               item['path'] in ('LICENSE.md', 'README.md', 'Assets/Editor/FixRocketboxMaxImport.cs'))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(fetch, wanted))
    manifest = {'source': 'https://github.com/microsoft/Microsoft-Rocketbox', 'revision': REVISION,
                'license': 'MIT; preserve LICENSE.md', 'characters': NAMES,
                'status': 'Downloaded candidates; not production-integrated; visual improvement unproven', 'files': files}
    (OUT / 'acquisition.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Done: {len(NAMES)} characters, {len(files)} files, {sum(f["bytes"] for f in files)/1e6:.1f} MB', flush=True)
