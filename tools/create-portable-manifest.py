"""Record the exact local, previously tested model snapshots for release setup."""
import hashlib
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 ('HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF','993a5971fda8f30dd1b7eb2654792ba4415c7460','.cache/models/qwen'),
 ('multimodalart/higgs-audio-v3-tts-4b-transformers','30f01593ee6a12efa586c92455afe4b76e45095d','.cache/higgs-transformers'),
 ('bosonai/higgs-audio-v2-tokenizer','403fbacf2f60caaa102f893fdfabb694619b2417','.cache/higgs-audio-v2-tokenizer'),
 ('dropbox-dash/faster-whisper-large-v3-turbo','0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf','.cache/whisper/large-v3-turbo'),
]


def main():
    manifest=dict(version=3,python='3.12.13',uv=dict(
        url='https://github.com/astral-sh/uv/releases/download/0.11.23/uv-x86_64-pc-windows-msvc.zip',
        sha256='02ad29f07e674d68726ba3bb1ff25b335d83515756e2b1a194bb56c3cc30e07c'),models=[],runtimes=[])
    for repo,revision,destination in SOURCES:
        files=[]
        for path in sorted((ROOT/destination).iterdir()):
            if not path.is_file() or path.name.startswith('.'):continue
            if destination=='.cache/models/qwen' and path.name not in ('Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf','README.md'):continue
            with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
            files.append(dict(name=path.name,bytes=path.stat().st_size,sha256=sha))
        manifest['models'].append(dict(repo=repo,revision=revision,destination=destination,files=files))
    variant=copy.deepcopy(manifest['models'][0])
    path=ROOT/'.cache/models/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf'
    with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    variant['files']=[f for f in variant['files'] if not f['name'].endswith('.gguf')]
    variant['files'].insert(0,dict(name=path.name,bytes=path.stat().st_size,sha256=sha))
    manifest['dialogue_variants']=[variant]
    fast=dict(repo='HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive',
              revision='0a41c68809d375475f954be12ba7c40efa56c2a9',destination='.cache/models/qwen9b',files=[])
    for name in ['Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q6_K.gguf','README.md']:
        path=ROOT/fast['destination']/name
        with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        fast['files'].append(dict(name=name,bytes=path.stat().st_size,sha256=sha))
    manifest['dialogue_variants'].append(fast)
    runtime=json.loads((ROOT/'docs/generated/llama-runtime.json').read_text())
    for index,row in enumerate(runtime['files']):
        manifest['runtimes'].append(dict(row,destination='.tools/llama',
            executable='.tools/llama/'+('llama-server.exe' if index==0 else 'cudart64_13.dll'),
            required=['.tools/llama/ggml-cuda.dll','.tools/llama/llama-server-impl.dll'] if index==0 else ['.tools/llama/cublas64_13.dll','.tools/llama/cublasLt64_13.dll']))
    lip=json.loads((ROOT/'docs/generated/rhubarb-runtime.json').read_text())
    manifest['runtimes'].append(dict(name=lip['url'].rsplit('/',1)[1],url=lip['url'],sha256=lip['sha256'],
        destination='.tools/rhubarb',executable=lip['executable'].replace('\\','/')))
    (ROOT/'services/portable-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Pinned model bytes:',sum(f['bytes'] for m in manifest['models'] for f in m['files']))


if __name__=='__main__':main()
