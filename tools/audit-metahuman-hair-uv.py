import bpy,json
from pathlib import Path
root=Path('D:/AI/Psychology_VR/experiments/metahuman/exports/unity');rows={}
for p in root.glob('*/models/*_cards_*.fbx'):
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(p))
 mesh=next(o.data for o in bpy.data.objects if o.type=='MESH');names=[u.name for u in mesh.uv_layers]
 channel=next((i for i,n in enumerate(names) if 'lightmap' not in n.lower()),0)
 rows[p.relative_to(root).as_posix()]={'names':names,'channel':channel}
(root/'hair-uv-channels.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows))
