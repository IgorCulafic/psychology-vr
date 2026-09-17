"""Install the pinned official Rhubarb CLI locally, retaining its notices."""
import hashlib,json,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TAG='v1.14.0'
folder=ROOT/'.tools/rhubarb';folder.mkdir(parents=True,exist_ok=True)
request=urllib.request.Request('https://api.github.com/repos/DanielSWolf/rhubarb-lip-sync/releases/tags/'+TAG,headers={'User-Agent':'PsychologyVR'})
release=json.load(urllib.request.urlopen(request))
asset=next(a for a in release['assets'] if 'Windows' in a['name'] and a['name'].endswith('.zip'))
archive=folder/asset['name'];urllib.request.urlretrieve(asset['browser_download_url'],archive)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
if asset.get('digest') and asset['digest']!='sha256:'+digest:raise RuntimeError('Release checksum mismatch')
with zipfile.ZipFile(archive) as z:
    for info in z.infolist():
        if not (folder/info.filename).resolve().is_relative_to(folder.resolve()):raise RuntimeError('Invalid archive path')
    z.extractall(folder)
exe=next(folder.rglob('rhubarb.exe'))
(ROOT/'docs/generated/rhubarb-runtime.json').write_text(json.dumps({'release':TAG,'url':asset['browser_download_url'],'sha256':digest,'executable':str(exe.relative_to(ROOT))},indent=2))
print(exe)
