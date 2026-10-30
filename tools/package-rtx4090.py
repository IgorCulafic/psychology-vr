"""Package an already staged full application with pinned weights and a file manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=Path,default=ROOT/'dist/PsychologyVR-i9-13900K-RTX4090/PsychologyVR')
    parser.add_argument('--output',type=Path,default=ROOT/'dist/PsychologyVR-Gemma4-12B-Q8-i9-13900K-RTX4090.zip')
    args=parser.parse_args();stage=args.stage.resolve();output=args.output.resolve()
    if output.is_relative_to(stage):raise ValueError('ZIP output must be outside its input directory')
    required=['unity/Builds/Windows/AlexPrototype.exe','voices/cast.json','services/config.local.json',
              '.cache/models/gemma4-12b-q8/gemma-4-12B-it-Q8_0.gguf','Optimization Settings.cmd']
    for name in required:
        if not (stage/name).is_file():raise FileNotFoundError(name)
    config=json.loads((stage/'services/config.local.json').read_text(encoding='utf-8-sig'))
    if config['dialogue_model']!='gemma-q8':raise ValueError('Gemma Q8 must be the primary model')
    files=[]
    for path in stage.rglob('*'):
        if not path.is_file():continue
        rel=path.relative_to(stage)
        if any(part in ('.runtime','__pycache__','.git','logs','Library') for part in rel.parts):continue
        if path.suffix in ('.pyc','.download','.partial','.log'):continue
        files.append(path)
    record=dict(upstream_commit='e170024ab3ec8750818f547e2372207c350c8f86',
        upstream_release='v0.5.0-metahuman-cast',target='i9-13900K, 64 GB RAM, RTX 4090 24 GB',
        primary_model='Gemma 4 12B Q8_0',voice_precision=config['higgs_quantization'],
        target_latency_seconds=15,target_latency_verified=False,files=[])
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=3) as bundle:
        for index,path in enumerate(sorted(files)):
            rel=path.relative_to(stage).as_posix()
            # Quantized weights and compressed movies gain little from re-compression.
            mode=zipfile.ZIP_STORED if path.suffix in ('.gguf','.safetensors','.bin','.mp4','.zip') else zipfile.ZIP_DEFLATED
            bundle.write(path,'PsychologyVR/'+rel,compress_type=mode)
            record['files'].append(dict(path=rel,bytes=path.stat().st_size,sha256=sha(path)))
            if index%100==0:print(f'Packaged {index+1}/{len(files)} files',flush=True)
        bundle.writestr('PsychologyVR/PACKAGE-MANIFEST.json',json.dumps(record,indent=2)+'\n')
    print('Checking ZIP CRCs...',flush=True)
    with zipfile.ZipFile(output) as bundle:
        bad=bundle.testzip()
        if bad:raise ValueError('ZIP CRC failure: '+bad)
    record.update(file=output.name,bytes=output.stat().st_size,sha256=sha(output),zip_crc_verified=True)
    manifest=output.with_suffix('.manifest.json');manifest.write_text(json.dumps(record,indent=2)+'\n')
    output.with_suffix('.sha256').write_text(record['sha256']+'  '+output.name+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='files'}),flush=True)

if __name__=='__main__':main()
