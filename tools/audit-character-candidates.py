import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
report=[]
files=list((R/'jumper_man').rglob('*.fbx'))+list((R/'Characters_with_expressions/FBX').rglob('*.Fbx'))
for path in files:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    item={'file':str(path.relative_to(R)),'meshes':[],'armatures':[],'actions':[]}
    for o in meshes:
        shapes=[]
        if o.data.shape_keys:
            base=o.data.shape_keys.key_blocks[0]
            for k in o.data.shape_keys.key_blocks[1:]:
                delta=[(v.co-base.data[i].co).length for i,v in enumerate(k.data)]
                shapes.append({'name':k.name,'moved':sum(d>1e-6 for d in delta),'max_delta':max(delta,default=0)})
        item['meshes'].append({'name':o.name,'vertices':len(o.data.vertices),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),'shapes':shapes,'materials':[m.name for m in o.data.materials if m]})
    for a in bpy.data.objects:
        if a.type=='ARMATURE':item['armatures'].append({'name':a.name,'bones':[b.name for b in a.data.bones]})
    item['actions']=[{'name':a.name,'frames':list(a.frame_range)} for a in bpy.data.actions]
    item['images']=[{'name':i.name,'path':i.filepath,'packed':bool(i.packed_file)} for i in bpy.data.images]
    report.append(item)
    (R/'docs/generated/candidate-rig-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('AUDITED',path.name,'shapes',sum(len(m['shapes']) for m in item['meshes']),flush=True)
