"""Build the small service/settings overlay; the complete base application is required."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['services/alex_service.py','services/higgs_service.py','services/higgs_decode.py',
 'services/voice_cast.py','services/speech_reuse.py','services/latency_metrics.py',
 'services/diagnostics_export.py','services/dialogue-models.json',
 'services/config.rtx4090-latency.example.json','services/licenses/HIGGS-AUDIO-V3.txt',
 'tools/optimization-settings.py','tools/optimization-settings.ps1',
 'tools/benchmark-response.py','tools/benchmark-response.ps1','tools/benchmark-higgs.py',
 'tools/check-gpu-memory.ps1','Check GPU Memory.cmd','docs/RTX4090_LATENCY_AUDIT.md',
 'docs/RTX4090_PACKAGE.md','docs/LATENCY_15_SECONDS_MONTENEGRIN.md',
 'docs/benchmarks/2026-10-17-latency-audit.json','tools/package-latency-update.py',
 'tools/enable-recorded-speech.py','tools/enable-recorded-speech.ps1','Enable Recorded Speech.cmd',
 'tools/benchmark-recorded-speech.py','tools/build-recorded-speech-library.py',
 'docs/RECORDED_SPEECH_OPTIMIZATION.md']
README='''Psychology VR latency audit update - v0.5.3

This is an overlay for the complete v0.5.1 application or v0.5.2 patched installation.
It does not include the game, Python installation or model weights.

1. Close the game and run Stop Services.cmd.
2. Merge this PsychologyVR folder's contents into the existing application folder.
   Your services/config.local.json is not included or replaced.
3. Read docs/RTX4090_LATENCY_AUDIT.md (or the included PDF).
4. Q8 + BF16 experiment: Optimization Settings.cmd -> 13. Requires validation on 4090.
5. Optional smaller dialogue model: PC Settings.cmd -> 6 (installs QAT Q4 if missing),
   then Optimization Settings.cmd -> 8 (QAT Q4, BF16 voices, sentence delivery).
6. Benchmark Responses.cmd measures prepared WAVs. Also test actual audible game replies.

The <=14-second 4090 target is NOT verified. The test machine was an RTX 3080 10 GB.
The source/default package remains Q8. QAT Q4 is an explicitly optional comparison.
Settings changes create backups under services/.runtime/config-backups.
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist/PsychologyVR-Latency-Audit-Update.zip')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--source-commit',default='working-tree')
    args=parser.parse_args()
    files=[(ROOT/name,name) for name in FILES]
    files.extend((p,p.relative_to(ROOT).as_posix()) for p in sorted((ROOT/'voices/recorded').rglob('*')) if p.is_file())
    if args.report:files.append((args.report,'docs/PsychologyVR_Latency_Audit_14s.pdf'))
    manifest=dict(version='0.5.3',type='overlay, base application required',source_commit=args.source_commit,
        target_seconds=14,target_4090_verified=False,contains_weights=False,replaces_local_configuration=False,files=[])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for path,relative in files:
            if not path.is_file():raise FileNotFoundError(path)
            if relative.endswith('config.local.json') or '.runtime/' in relative:raise ValueError('Private file in package')
            data=path.read_bytes()
            manifest['files'].append(dict(path=relative,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            bundle.writestr('PsychologyVR/'+relative,data)
        bundle.writestr('PsychologyVR/README-LATENCY-UPDATE.txt',README)
        bundle.writestr('PsychologyVR/LATENCY-UPDATE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(args.output) as bundle:
        if bundle.testzip():raise ValueError('ZIP CRC failure')
        for row in manifest['files']:
            assert hashlib.sha256(bundle.read('PsychologyVR/'+row['path'])).hexdigest()==row['sha256']
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix('.sha256').write_text(digest+'  '+args.output.name+'\n',encoding='utf-8')
    args.output.with_suffix('.manifest.json').write_text(json.dumps(dict(manifest,zip_sha256=digest,
        zip_bytes=args.output.stat().st_size,zip_crc_verified=True),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(args.output),bytes=args.output.stat().st_size,sha256=digest,crc_verified=True)))


if __name__=='__main__':main()
