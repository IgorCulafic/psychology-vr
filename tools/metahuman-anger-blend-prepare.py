"""Prepare isolated variants and inspect the speech/anger mouth controls."""
import json
from pathlib import Path
import unreal
root=Path(__file__).resolve().parents[1]/'experiments/metahuman'
out=root/'anger-blend';out.mkdir(exist_ok=True)
take=next(t for t in json.loads((root/'speaking/manifest.json').read_text(encoding='utf-8')) if t['name']=='angry')
(out/'manifest.json').write_text(json.dumps([take],indent=2),encoding='utf-8')
report={}
for title,path in [('speech','/Game/Audition/Speaking/angry/LS_Audio'),('recording','/Game/Audition/Sequences/LS_Closeup_angry')]:
    seq=unreal.load_asset(path);report[title]={}
    for b in seq.get_bindings():
        if str(b.get_display_name())!='Face':continue
        for t in b.get_tracks():
            for s in t.get_sections():
                for c in s.get_all_channels():
                    name=str(c.get_editor_property('channel_name'))
                    if not any(k in name.lower() for k in ['jaw','lipstogether','lipspress','upperlipraise','lowerlipdepress','stretchlipsclose','cornerpull','stretch']):continue
                    vals=[float(k.get_value()) for k in c.get_keys()]
                    if vals:report[title][name]={'min':min(vals),'max':max(vals)}
for variant in ['balanced','shout']:
    for prefix in ['LS_Control_','LS_']:
        path='/Game/Audition/AngerBlend/'+prefix+variant
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            seq=unreal.EditorAssetLibrary.duplicate_asset('/Game/Audition/Sequences/LS_Closeup_angry',path)
            unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
(out/'prepare-report.json').write_text(json.dumps(report,indent=2))
