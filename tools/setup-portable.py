"""Install pinned model/runtime downloads and validate an extracted Windows release."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MODEL_PREFIX='Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-'
HARDWARE_PRESETS={
    'quality':dict(llm_model_path='.cache/models/qwen/'+MODEL_PREFIX+'IQ4_XS.gguf',llm_gpu_layers=48),
    'rtx4090':dict(llm_model_path='.cache/models/qwen/'+MODEL_PREFIX+'IQ3_M.gguf',llm_gpu_layers=32),
    'fast9b':dict(llm_model_path='.cache/models/qwen9b/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q6_K.gguf',llm_gpu_layers=99),
}


def resolve_preset(requested,total_bytes):
    if requested not in ('auto',*HARDWARE_PRESETS):raise RuntimeError('Unknown hardware_preset; choose auto, quality, rtx4090 or fast9b in PC Settings.cmd.')
    if total_bytes<23*1024**3:raise RuntimeError('These BF16 speech presets require a single NVIDIA GPU with at least 24 GB VRAM.')
    return ('quality' if total_bytes>=30*1024**3 else 'rtx4090') if requested=='auto' else requested


def gpu_properties():
    import torch
    if not torch.cuda.is_available():raise RuntimeError('An NVIDIA GPU and current NVIDIA driver are required.')
    properties=torch.cuda.get_device_properties(0)
    return properties.name,properties.total_memory


def selected_manifest(manifest,config):
    selected=copy.deepcopy(manifest)
    model_path=config.get('llm_model_path',HARDWARE_PRESETS['quality']['llm_model_path'])
    if config.get('dialogue_model'):
        catalog=json.loads((ROOT/'services/dialogue-models.json').read_text(encoding='utf-8'))['models']
        choice=next((m for m in catalog if m['id']==config['dialogue_model']),None)
        if choice is None:raise RuntimeError('Unknown dialogue_model in configuration.')
        model_path=choice['model_path']
        if choice['id']=='bonsai':selected['runtimes']+=copy.deepcopy(selected['bonsai_runtimes'])
    model=selected['models'][0]
    for variant in [model,*selected.get('dialogue_variants',[])]:
        if any(model_path==variant['destination']+'/'+f['name'] for f in variant['files']):
            selected['models'][0]=copy.deepcopy(variant)
            return selected
    raise RuntimeError('Configured dialogue model is not in the download manifest. Select a supported preset in PC Settings.cmd.')


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


def configure(preset=None,model=None):
    config_path=ROOT/'services/config.local.json'
    defaults=json.loads((ROOT/'services/config.expressive.example.json').read_text(encoding='utf-8-sig'))
    portable_paths=dict(bridge_python='.tools/portable-env/Scripts/python.exe',
                        higgs_python='.tools/portable-env/Scripts/python.exe',
                        higgs_reference='voices/reference.wav')
    defaults.update(portable_paths)
    original=config_path.read_bytes() if config_path.exists() else None
    try:
        existing=json.loads(original.decode('utf-8-sig')) if original is not None else {}
    except (ValueError,UnicodeError) as error:
        raise RuntimeError('services/config.local.json is not valid JSON. Correct it or rename it to keep a backup, then rerun Setup.cmd.') from error
    if not isinstance(existing,dict):
        raise RuntimeError('services/config.local.json must contain a JSON object. Rename it to keep a backup, then rerun Setup.cmd.')
    # Older/source configurations may lack speech or portable-runtime settings.
    # Fill missing fields while retaining explicit provider/voice/user choices.
    config={**defaults,**existing}
    for key,value in portable_paths.items():
        if config[key] is None or (isinstance(config[key],str) and not config[key].strip()):config[key]=value
        if not isinstance(config[key],str):raise RuntimeError(f'{key} in services/config.local.json must be a file path.')
    reference=ROOT/config['higgs_reference']
    if not reference.is_file() or not reference.with_suffix('.json').is_file():
        raise RuntimeError('Voice reference missing. Place reference.wav and reference.json in voices/ (see START HERE.md).')
    transcript=json.loads(reference.with_suffix('.json').read_text(encoding='utf-8-sig')).get('text')
    if not isinstance(transcript,str) or not transcript.strip():raise RuntimeError('Voice transcript is empty.')
    if preset is not None:
        config['hardware_preset']=preset
        config['dialogue_model']='' # Explicit legacy hardware preset selects its own quant.
    if model is not None:config['dialogue_model']=model
    if config.get('hardware_preset'):
        gpu_name,total_bytes=gpu_properties()
        resolved=resolve_preset(config['hardware_preset'],total_bytes)
        config.update(HARDWARE_PRESETS[resolved])
        config['hardware_preset_resolved']=resolved
        print(f"GPU: {gpu_name} ({total_bytes/1024**3:.1f} GiB); preset: {config['hardware_preset']} -> {resolved}; dialogue GPU layers: {config['llm_gpu_layers']}",flush=True)
    if config.get('dialogue_model'):
        catalog=json.loads((ROOT/'services/dialogue-models.json').read_text(encoding='utf-8'))['models']
        choice=next((m for m in catalog if m['id']==config['dialogue_model']),None)
        if choice is None:raise RuntimeError('Unknown dialogue_model in configuration.')
        config.update(llm_model_path=choice['model_path'],llm_gpu_layers=choice['gpu_layers'])
        print(f"Dialogue selection: {choice['label']} ({choice['gpu_layers']} GPU layers); speech quality unchanged.",flush=True)
    if original is None or config!=existing:
        if original is not None:
            backup=ROOT/'services/.runtime/config-backups'/f'config-{time.time_ns()}.json'
            backup.parent.mkdir(parents=True,exist_ok=True)
            backup.write_bytes(original)
            print('Updated setup settings; previous configuration saved to '+str(backup),flush=True)
        temporary=config_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temporary.replace(config_path)
    return config


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
    parser.add_argument('--preset',choices=['auto',*HARDWARE_PRESETS])
    parser.add_argument('--model',choices=['bonsai','gemma','qwen'],help='Install/select an in-game dialogue model; keeps speech quality unchanged')
    parser.add_argument('--configure-only',action='store_true',help='Resolve GPU settings without downloading or starting services')
    parser.add_argument('--verify-files',action='store_true',help='Check model hashes without loading libraries')
    args=parser.parse_args();manifest=json.loads((ROOT/'services/portable-manifest.json').read_text(encoding='utf-8'))
    config=configure(args.preset,args.model)
    manifest=selected_manifest(manifest,config)
    if args.configure_only:return
    if args.verify_files:validate_files(manifest,True);print('MODEL_CHECKSUMS_OK');return
    if not args.check:
        doctor(False)
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
    doctor()
    print('PORTABLE_READY',flush=True)


if __name__=='__main__':main()
