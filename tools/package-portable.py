"""Package a standalone Windows release. Voice inclusion is an explicit option."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-approved-voice',action='store_true')
    parser.add_argument('--tag',default='v0.2.3-fast-dialogue')
    args=parser.parse_args();out=ROOT/'.cache/releases'/args.tag;out.mkdir(parents=True,exist_ok=True)
    files={}
    def add(path,name=None):files[name or path.relative_to(ROOT).as_posix()]=path
    for path in ROOT.glob('*.cmd'):add(path)
    for name in ['START HERE.md','ASSET_CREDITS.md','docs/GPU_PRESETS.md']:add(ROOT/name)
    for folder in ['services','characters']:
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(ROOT/folder).parts):continue
            if path.name=='config.local.json' or path.name.startswith('test_') or path.suffix=='.pyc':continue
            add(path)
    for name in ['run-portable.ps1','setup-portable.py','launch.ps1','launch-text-chat.ps1','stop-services.ps1']:
        add(ROOT/'tools'/name)
    for name in ['EmotionCatalog.json','ScenarioCatalog.json']:
        add(ROOT/'unity/Assets/PsychologyVR/Resources'/name)
    for path in (ROOT/'unity/Builds/Windows').rglob('*'):
        if path.is_file() and not any('BackUpThisFolder' in p for p in path.parts) and path.suffix not in ('.log','.pdb'):add(path)
    uv=ROOT/'.cache/releases/uv-0.11.23.zip'
    manifest=json.loads((ROOT/'services/portable-manifest.json').read_text())
    if sha(uv)!=manifest['uv']['sha256']:raise ValueError('Wrong UV installer archive')
    add(uv,'.tools/bootstrap/uv.zip')
    for license in ['MIT','APACHE']:
        add(ROOT/'.cache/releases'/('uv-LICENSE-'+license),'THIRD_PARTY/uv/LICENSE-'+license)
    if args.include_approved_voice:
        base=ROOT/'docs/generated/fish-local/references/clone-test-1'
        for suffix in ('.wav','.json'):add(base.with_suffix(suffix),'voices/reference'+suffix)
    required=['unity/Builds/Windows/AlexPrototype.exe','services/portable-manifest.json','Start VR.cmd','Start Desktop.cmd']
    if not all(name in files for name in required):raise ValueError('Release is incomplete')
    archive=out/'psychology-vr-windows.zip';rows=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as bundle:
        for name,path in sorted(files.items()):
            if not path.is_file():raise FileNotFoundError(path)
            bundle.write(path,'PsychologyVR/'+name)
            rows.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip():raise ValueError('Release archive failed CRC verification')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    record=dict(tag=args.tag,commit=commit,private_voice_included=args.include_approved_voice,
                file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),files=rows)
    repair=out/'pc-settings-update.zip'
    with zipfile.ZipFile(repair,'w',zipfile.ZIP_DEFLATED) as bundle:
        for name in ['PC Settings.cmd','tools/setup-portable.py','tools/run-portable.ps1','tools/launch.ps1',
                     'services/config.expressive.example.json','services/portable-manifest.json','services/alex_service.py','docs/GPU_PRESETS.md']:
            bundle.write(ROOT/name,name)
        bundle.writestr('APPLY PC SETTINGS UPDATE.txt',
            'Close the game. Extract this ZIP into your existing application folder, replacing matching files.\r\n'
            'Double-click PC Settings.cmd and choose 4 (Fast dialogue) to try the smaller fully-GPU model.\r\n'
            'This stops this copy\'s AI services. Auto and both existing 27B presets remain available.\r\n'
            'A 24 GB GPU selects IQ3_M / 32 GPU layers; 32 GB+ selects IQ4_XS / 48. BF16 voice is unchanged.\r\n'
            'Keep .tools, .cache, voices and logs. Setup reuses verified models and installs only the selected dialogue quant.\r\n'
            'Fast dialogue downloads 7.4 GB once. The 27B IQ3_M option downloads 12.8 GB once. Old models are kept.\r\n'
            'Fast is opt-in: compare language and character behavior before use with students.\r\n'
            'Original configuration is backed up under services/.runtime/config-backups/. Start VR/Desktop after setup.\r\n'
            'This patch does not contain the game or voice. For a new installation, use psychology-vr-windows.zip.\r\n')
    record['pc_settings_update']=dict(file=repair.name,bytes=repair.stat().st_size,sha256=sha(repair))
    record_path=out/'release-manifest.json';record_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(f"{record['sha256']}  {archive.name}\n{sha(record_path)}  {record_path.name}\n{sha(repair)}  {repair.name}\n",encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='files'}),flush=True)


if __name__=='__main__':main()
