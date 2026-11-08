"""Install only the pinned upstream player/voice assets into a source checkout."""
import hashlib
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/IgorCulafic/psychology-vr/releases/download/v0.5.0-metahuman-cast/psychology-vr-windows.zip'
SHA='b3c44e01eb55e3af65cca464e358c6c4e8a09be833c5fa24518830735439c553'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    if (ROOT/'unity/Builds/Windows/AlexPrototype.exe').is_file():return
    cache=ROOT/'.cache';cache.mkdir(exist_ok=True)
    archive=cache/'upstream-v0.5.0-player.zip'
    if not archive.exists() or sha(archive)!=SHA:
        part=archive.with_suffix('.zip.download')
        print('Downloading the pinned complete Windows player (1.36 GB)...',flush=True)
        urllib.request.urlretrieve(URL,part)
        if sha(part)!=SHA:raise ValueError('Upstream player checksum mismatch')
        part.replace(archive)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if entry.is_dir() or not entry.filename.startswith('PsychologyVR/'):continue
            name=entry.filename[len('PsychologyVR/'):]
            voice_asset=name.startswith('voices/runtime/') or name in ('voices/reference.wav','voices/reference.json','voices/cast.json','voices/README.md')
            if not (name.startswith('unity/Builds/Windows/') or voice_asset):continue
            target=(ROOT/name).resolve()
            if not target.is_relative_to(ROOT):raise ValueError('Unsafe archive member')
            if target.exists() and name.startswith('voices/'):continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with bundle.open(entry) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
    if not (ROOT/'unity/Builds/Windows/AlexPrototype.exe').is_file():raise ValueError('Player missing from pinned archive')
    print('Pinned player and approved voice assets ready.',flush=True)

if __name__=='__main__':main()
