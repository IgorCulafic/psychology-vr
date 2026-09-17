"""Create a local speech fixture for visual playback checks; no LLM is used."""
import json,sys,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge
config=json.loads((ROOT/'services/config.local.json').read_text())
bridge=Bridge(config)
segment={'text':'I feel a little safer here. But when I hear a loud noise, I still think about the earthquake.',
         'emotion':'anxious','intensity':.55,'gesture':'none','voice_style':'hesitant'}
start=time.perf_counter();bridge.synthesize(segment,'facial-demo')
segment['mouth_cues'],source=bridge.align_mouth('facial-demo',segment['text'])
if source!='rhubarb' or not segment['mouth_cues']:raise RuntimeError('Real alignment required for fixture')
dest=ROOT/'unity/Assets/PsychologyVR/Resources/FaceDemo';dest.mkdir(parents=True,exist_ok=True)
shutil.copy2(bridge.runtime/'facial-demo.wav',dest/'speech.wav')
segment['lip_sync_source']=source
(dest/'speech.json').write_text(json.dumps(segment,indent=2))
(ROOT/'docs/generated/facial-speech-fixture.json').write_text(json.dumps({'source':source,'cue_count':len(segment['mouth_cues']),
    'shapes':sorted(set(c['value'] for c in segment['mouth_cues'])),'preparation_seconds':time.perf_counter()-start,'text':segment['text']},indent=2))
print('FACIAL_SPEECH_FIXTURE_OK',source,len(segment['mouth_cues']))
