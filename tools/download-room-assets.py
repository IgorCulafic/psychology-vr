"""Download a small, credited CC0 selection through Poly Haven's public API."""
import hashlib
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/assets/polyhaven'
MODELS = ['modern_arm_chair_01', 'side_table_01', 'modern_coffee_table_01',
          'small_wooden_table_01', 'potted_plant_01', 'potted_plant_02',
          'binder_notebook', 'modern_ceiling_lamp_01']

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'PsychologyVR-asset-import/1.0'}), timeout=90).read()

def download(item, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or hashlib.md5(target.read_bytes()).hexdigest() != item['md5']:
        data = get(item['url'])
        if hashlib.md5(data).hexdigest() != item['md5']:
            raise ValueError('Checksum mismatch: ' + item['url'])
        target.write_bytes(data)

def model(asset):
    folder = CACHE / asset
    folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(get('https://api.polyhaven.com/files/' + asset))
    (folder / 'files.json').write_text(json.dumps(metadata, indent=2))
    item = metadata['gltf']['1k']['gltf']
    download(item, folder / (asset + '.gltf'))
    for relative, included in item.get('include', {}).items():
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder.resolve()):
            raise ValueError('Invalid asset path')
        download(included, target)
    print('Downloaded ' + asset, flush=True)
    return {'id':asset, 'source':'https://polyhaven.com/a/'+asset, 'license':'CC0-1.0',
            'resolution':'1k', 'files':item}

def surface(asset):
    folder=CACHE/asset
    folder.mkdir(parents=True,exist_ok=True)
    metadata=json.loads(get('https://api.polyhaven.com/files/'+asset))
    items={}
    for channel,key in [('diff','Diffuse'),('nor_gl','nor_gl'),('rough','Rough')]:
        item=metadata[key]['1k']['jpg']
        download(item,folder/(asset+'_'+channel+'.jpg'))
        items[channel]=item
    return {'id':asset,'source':'https://polyhaven.com/a/'+asset,'license':'CC0-1.0','resolution':'1k','files':items}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(model, MODELS))
        records += list(pool.map(surface,['wood_floor','white_plaster_02']))
    (ROOT / 'docs/generated/room-asset-sources.json').write_text(json.dumps(records, indent=2))
