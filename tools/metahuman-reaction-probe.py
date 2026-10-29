import json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
report={}
for name in ['afraid','crying','angry']:
    seq=unreal.load_asset('/Game/Audition/Sequences/LS_Closeup_'+name)
    rows=[]
    for binding in seq.get_bindings():
        row={'name':str(binding.get_display_name()),'tracks':[]}
        for track in binding.get_tracks():
            tr={'class':track.get_class().get_name(),'channels':[]}
            for section in track.get_sections():
                for channel in section.get_all_channels():
                    label=str(channel.get_name())
                    if any(s in label.lower() for s in ['head','neck','switch','transform','rotation']):
                        keys=channel.get_keys()
                        vals=[str(k.get_value()) for k in keys]
                        tr['channels'].append({'name':label,'keys':len(keys),'first':vals[:2],'last':vals[-2:], 'unique':len(set(vals)),'default':str(channel.get_default())})
            row['tracks'].append(tr)
        rows.append(row)
    report[name]=rows
report['export_options_doc']=unreal.AnimSeqExportOption.__doc__
report['anim_library_methods']=[x for x in dir(unreal.AnimationLibrary) if any(t in x for t in ['bone','curve','track'])]
(ROOT/'experiments/metahuman/reaction-probe.json').write_text(json.dumps(report,indent=2))
