"""Install pinned model/runtime downloads and validate an extracted Windows release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def contained(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Path leaves the application folder')
    return path


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def extract(archive,destination):
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():contained(destination,member.filename)
        bundle.extractall(destination)


def download_runtime(entry):
    destination=contained(ROOT,entry['destination'])
    executable=contained(ROOT,entry['executable'])
    if executable.is_file() and all(contained(ROOT,p).is_file() for p in entry.get('required',[])):return
    destination.mkdir(parents=True,exist_ok=True)
    archive=destination/entry['name']
    if not archive.is_file() or digest(archive)!=entry['sha256']:
        temporary=archive.with_suffix('.download')
        print('Downloading '+entry['name'],flush=True)
        urllib.request.urlretrieve(entry['url'],temporary)
        if digest(temporary)!=entry['sha256']:raise ValueError('Runtime checksum mismatch: '+entry['name'])
        temporary.replace(archive)
    extract(archive,destination)


def validate_files(manifest,full=False):
    for model in manifest['models']:
        for entry in model['files']:
            path=contained(ROOT,model['destination']+'/'+entry['name'])
            if not path.is_file() or path.stat().st_size!=entry['bytes']:
                raise RuntimeError('Missing or incomplete model: '+str(path)+'; rerun Setup.cmd.')
            if full and digest(path)!=entry['sha256']:raise RuntimeError('Model checksum mismatch: '+str(path))
    for runtime in manifest['runtimes']:
        for file in [runtime['executable'],*runtime.get('required',[])]:
            if not contained(ROOT,file).is_file():raise RuntimeError('Missing runtime: '+file)


def configure():
    config_path=ROOT/'services/config.local.json'
    if not config_path.exists():
        config=json.loads((ROOT/'services/config.expressive.example.json').read_text(encoding='utf-8'))
        config.update(bridge_python='.tools/portable-env/Scripts/python.exe',higgs_python='.tools/portable-env/Scripts/python.exe',higgs_reference='voices/reference.wav')
        config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    reference=ROOT/config['higgs_reference']
    if not reference.is_file() or not reference.with_suffix('.json').is_file():
        raise RuntimeError('Voice reference missing. Place reference.wav and reference.json in voices/ (see START HERE.md).')
    transcript=json.loads(reference.with_suffix('.json').read_text(encoding='utf-8-sig')).get('text')
    if not isinstance(transcript,str) or not transcript.strip():raise RuntimeError('Voice transcript is empty.')


def doctor(check_runtime=True):
    import torch
    import torchaudio
    import transformers
    import soundfile
    import faster_whisper
    config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
    if soundfile.info(ROOT/config['higgs_reference']).duration<3:raise RuntimeError('Voice reference is too short.')
    if not torch.cuda.is_available():raise RuntimeError('An NVIDIA GPU and current NVIDIA driver are required for this BF16 release.')
    if not torch.cuda.is_bf16_supported():raise RuntimeError('This GPU does not support the selected BF16 voice.')
    properties=torch.cuda.get_device_properties(0)
    print(f'GPU: {properties.name}, {properties.total_memory/1024**3:.1f} GB; speech: BF16',flush=True)
    if properties.total_memory<23*1024**3:raise RuntimeError('This full local-model preset requires an NVIDIA GPU with at least 24 GB VRAM.')
    if not (ROOT/'unity/Builds/Windows/AlexPrototype.exe').is_file():
        raise RuntimeError('Built game missing. Download the Windows release ZIP, not GitHub Source code.zip.')
    if check_runtime:
        subprocess.run([str(ROOT/'.tools/llama/llama-server.exe'),'--version'],check=True,timeout=30,
                       stdout=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--verify-files',action='store_true',help='Check model hashes without loading libraries')
    args=parser.parse_args();manifest=json.loads((ROOT/'services/portable-manifest.json').read_text(encoding='utf-8'))
    if args.verify_files:validate_files(manifest,True);print('MODEL_CHECKSUMS_OK');return
    if not args.check:
        configure();doctor(False)
        if shutil.disk_usage(ROOT).free<45*1024**3 and not all(contained(ROOT,m['destination']+'/'+m['files'][0]['name']).exists() for m in manifest['models']):
            raise RuntimeError('Allow at least 45 GB free disk space for the local AI setup.')
        hf=Path(sys.executable).with_name('hf.exe')
        for model in manifest['models']:
            print('Preparing '+model['repo'],flush=True)
            # Pinned revisions and an explicit file list avoid unrelated quantizations.
            missing=[];damaged=[]
            for entry in model['files']:
                path=contained(ROOT,model['destination']+'/'+entry['name'])
                if not path.exists():missing.append(entry['name'])
                elif path.stat().st_size!=entry['bytes'] or digest(path)!=entry['sha256']:damaged.append(entry['name'])
            for names,force in [(missing,False),(damaged,True)]:
                if names:
                    subprocess.run([str(hf),'download',model['repo'],*names,'--revision',model['revision'],
                        '--local-dir',str(contained(ROOT,model['destination'])),*(['--force-download'] if force else [])],check=True)
        for entry in manifest['runtimes']:download_runtime(entry)
        validate_files(manifest,True)
    else:validate_files(manifest)
    configure();doctor()
    print('PORTABLE_READY',flush=True)


if __name__=='__main__':main()
