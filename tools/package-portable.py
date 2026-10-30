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
    parser.add_argument('--include-voice-packs',action='store_true')
    parser.add_argument('--include-recorded-preview',action='store_true')
    parser.add_argument('--tag',default='v0.2.4-complete-package')
    args=parser.parse_args();out=ROOT/'.cache/releases'/args.tag;out.mkdir(parents=True,exist_ok=True)
    files={}
    def add(path,name=None):files[name or path.relative_to(ROOT).as_posix()]=path
    # These source-only tools need Unreal/editor or evaluation assets not in the player ZIP.
    for path in ROOT.glob('*.cmd'):
        if 'Unreal' in path.name or path.name=='Start Model Lab.cmd':continue
        if path.name=='Preview Recorded Face.cmd' and not args.include_recorded_preview:continue
        if path.name=='Preview Voices.cmd' and not args.include_voice_packs:continue
        add(path)
    for name in ['START HERE.md','ASSET_CREDITS.md','docs/SESSION_LOGGING.md','docs/GPU_PRESETS.md','docs/MODEL_SWITCHING.md','docs/GEMMA_VRAM.md','docs/QUEST_LINK_LIVE_TEST.md','docs/HEADSET_FREE_STRESS.md','docs/RELEASE_0_5_0.md','docs/RELEASE_0_5_1.md','docs/BRANCH_INTEGRATION_2026_10_21.md','docs/LIVE_EXPRESSIVE_SPEECH.md','docs/GEMMA_VS_ORIGINAL.md']:add(ROOT/name)
    for name in ['gemma-unity-vram.json','quest-link-live-vram.json','headset-free-stress-comparison.json',
                 'headset-free-stress/report.json','headset-free-stress-2400/report.json','headset-free-stress-2000/report.json',
                 'branch-integration-2026-10-21.json']:
        add(ROOT/'docs/generated'/name)
    for folder in ['services','characters']:
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(ROOT/folder).parts):continue
            if path.name=='config.local.json' or path.name.startswith('test_') or path.suffix=='.pyc':continue
            add(path)
    for name in ['run-portable.ps1','setup-portable.py','launch.ps1','launch-text-chat.ps1','stop-services.ps1','select-model.ps1','export-diagnostics.py','export-diagnostics.ps1','hardware-profile.py','hardware-profile.ps1','optimization-settings.py','optimization-settings.ps1','enable-recorded-speech.py','enable-recorded-speech.ps1']:
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
    if args.include_voice_packs:
        # Runtime packs are a narrow manifest allowlist of approved references.
        # Include them even before staging; never sweep raw voice recordings.
        from sys import path as import_path
        import_path.insert(0,str(ROOT/'services'))
        from voice_cast import VoiceCast
        cast=VoiceCast(ROOT)
        if not cast.scenarios:raise ValueError('Build assigned runtime voice packs first')
        add(ROOT/'voices/cast.json')
        registry=json.loads((ROOT/'voices/cast.json').read_text(encoding='utf-8'))
        for manifest_path in registry['speakers'].values():
            add(ROOT/manifest_path)
            pack=json.loads((ROOT/manifest_path).read_text(encoding='utf-8'))
            for recipe in pack['recipes'].values():
                ref=ROOT/recipe['reference']
                add(ref);add(ref.with_suffix('.json'))
        # Use the Git allowlist, never sweep local auditions or temporary recordings.
        tracked=subprocess.check_output(['git','ls-files','-z','--','voices'],cwd=ROOT).decode().split('\0')
        for name in filter(None,tracked):add(ROOT/name)
        # Include only the selected preset dependencies, not every local audition.
        for speaker in registry['speakers']:
            source=ROOT/'voices'/speaker/('cleaned' if speaker.startswith('igor') else 'prepared')
            for preset_path in source.glob('preferred_*.json'):
                preset=json.loads(preset_path.read_text(encoding='utf-8'))
                add(preset_path)
                for field in ['reference','audition_audio']:
                    if not preset.get(field):continue
                    dependency=(ROOT/preset[field]).resolve()
                    if not dependency.is_relative_to((ROOT/'voices').resolve()):
                        raise ValueError('Voice preview dependency outside voices')
                    add(dependency)
                    if dependency.with_suffix('.json').exists():add(dependency.with_suffix('.json'))
        for name in ['prepare-voice-pack.py','audition-voice-pack.py','refine-voice-delivery.py','build-voice-index.py']:
            add(ROOT/'tools'/name)
        add(ROOT/'docs/VOICE_RECORDING_SCRIPT_ME.md')
        for person in ['person_01','person_02','person_03']:
            if f'voices/{person}/prepared/preferred_anger.json' not in files:
                raise ValueError('Voice pack not committed/staged: '+person)
        if 'voices/index.html' not in files:raise ValueError('Voice listening index is missing')
    if args.include_recorded_preview:
        for path in (ROOT/'unity/Builds/LiveLinkPreview').rglob('*'):
            if path.is_file() and not any('BackUpThisFolder' in p for p in path.parts) and path.suffix not in ('.log','.pdb'):add(path)
        for name in ['extract-livelink-video.py','encode-livelink-preview.py','livelink-requirements.txt']:
            add(ROOT/'tools'/name)
        add(ROOT/'docs/RECORDED_FACE_POC.md')
        if 'unity/Builds/LiveLinkPreview/LiveLinkPreview.exe' not in files:
            raise ValueError('Recorded face preview player is missing')
    for name in ['docs/RELEASE_0_4_0.md','docs/UNREAL_PORT.md']:
        add(ROOT/name)
    add(ROOT/'output/pdf/Psychology_VR_pregled_projekta_CG.pdf','docs/PROJECT_OVERVIEW_CG.pdf')
    for name in ['person_03_happy_statistika.wav','person_03_happy_statistika.mp3','person_03_happy_statistika.json']:
        add(ROOT/'output/audio'/name)
    required=['unity/Builds/Windows/AlexPrototype.exe','services/portable-manifest.json','Start VR.cmd','Start Desktop.cmd',
              'Export Diagnostics.cmd','services/performance_log.py','services/diagnostics_export.py',
              'tools/export-diagnostics.py','tools/export-diagnostics.ps1','services/voice_cast.py','voices/cast.json']
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
    record=dict(tag=args.tag,commit=commit,approved_reference_voice_included=args.include_approved_voice,
                voice_packs_included=args.include_voice_packs,recorded_preview_player_included=args.include_recorded_preview,
                personal_capture_data_included=False,unreal_runtime_included=False,
                file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),files=rows)
    record_path=out/'release-manifest.json';record_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(f"{record['sha256']}  {archive.name}\n{sha(record_path)}  {record_path.name}\n",encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='files'}),flush=True)


if __name__=='__main__':main()
