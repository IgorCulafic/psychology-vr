"""Copy the approved, assigned auditions and calculate phonemes for the Unity check."""
import json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
cast=read('voices/cast.json')
for scenario,speaker in cast['scenarios'].items():
    manifest=read(cast['speakers'][speaker]);preset=read(manifest['recipes']['anger']['source_preset'])
    char=scenario.split('-')[0];dest=ROOT/f'unity/Assets/PsychologyVR/Art/MetaHumans/{char}/audio';dest.mkdir(exist_ok=True)
    wav=dest/'anger.wav';shutil.copy2(ROOT/preset['audition_audio'],wav)
    subprocess.run([str(ROOT/'.tools/rhubarb/Rhubarb-Lip-Sync-1.14.0-Windows/rhubarb.exe'),'-r','phonetic','-f','json','-o',str(dest/'anger.json'),str(wav)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (dest/'provenance.json').write_text(json.dumps({'scenario':scenario,'speaker':speaker,'source':preset['audition_audio'],'precision':'bf16'},indent=2))
    print(char,speaker,flush=True)
