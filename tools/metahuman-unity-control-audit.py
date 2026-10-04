import unreal,json
from pathlib import Path
s=unreal.load_asset('/Game/Audition/Unity/ivan/LS_poses')
b=next(b for b in s.get_bindings() if str(b.get_display_name())=='Face')
cs=[str(c.get_editor_property('channel_name')) for t in b.get_tracks() for sec in t.get_sections() for c in sec.get_all_channels()]
Path('D:/AI/Psychology_VR/experiments/metahuman/exports/unity/control-names.json').write_text(json.dumps(cs,indent=2))
unreal.SystemLibrary.quit_editor()
