"""Hydrate artwork from its pinned original repository without Git LFS setup."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def download(entry):
    target=(ROOT/entry['path']).resolve()
    if not target.is_relative_to(ROOT):raise ValueError('Asset leaves project')
    if target.is_file() and target.stat().st_size==entry['bytes']:
        with target.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()==entry['sha256']:return
    target.parent.mkdir(parents=True,exist_ok=True)
    url='https://media.githubusercontent.com/media/IgorCulafic/psychology-vr/e170024ab3ec8750818f547e2372207c350c8f86/'+urllib.parse.quote(entry['path'],safe='/')
    part=target.with_suffix(target.suffix+'.download')
    urllib.request.urlretrieve(url,part)
    with part.open('rb') as stream:
        if part.stat().st_size!=entry['bytes'] or hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:
            raise ValueError('Source asset checksum mismatch: '+entry['path'])
    part.replace(target)

def main():
    entries=json.loads((ROOT/'source-assets.json').read_text())['assets']
    print(f'Preparing {len(entries)} pinned art assets ({sum(e["bytes"] for e in entries)/1024**3:.1f} GiB).',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index,_ in enumerate(pool.map(download,entries),1):
            if index%25==0:print(f'{index}/{len(entries)} assets checked',flush=True)
    print('Source artwork ready. Open unity/ in Unity 6000.6.0f1.',flush=True)

if __name__=='__main__':main()
