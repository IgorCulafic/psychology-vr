import bpy,bmesh,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for part in ['SkeletalMesh','Body']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.fbx(filepath=str(ROOT/f'experiments/metahuman/exports/unity/ivan/models/{part}.fbx'))
 for o in bpy.context.scene.objects:
  if o.type=='ARMATURE':
   rows.append({'armature':o.name,'bones':{n:list(o.matrix_world@o.data.bones[n].head_local) for n in ['pelvis','thigh_l','calf_l','foot_l','ball_l'] if n in o.data.bones}})
  if o.type!='MESH':continue
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
  boundary=[e for e in bm.edges if e.is_boundary];todo=set(v for e in boundary for v in e.verts);loops=[]
  while todo:
   group={todo.pop()};stack=list(group)
   while stack:
    v=stack.pop()
    for e in v.link_edges:
     if not e.is_boundary:continue
     other=e.other_vert(v)
     if other in todo:todo.remove(other);group.add(other);stack.append(other)
   pts=[o.matrix_world@v.co for v in group]
   loops.append({'n':len(group),'min':[min(p[i] for p in pts) for i in range(3)],'max':[max(p[i] for p in pts) for i in range(3)]})
  rows.append({'part':part,'mesh':o.name,'verts':len(o.data.vertices),'materials':[(m.name if m else '') for m in o.data.materials],'bounds':[[min((o.matrix_world@v.co)[i] for v in o.data.vertices),max((o.matrix_world@v.co)[i] for v in o.data.vertices)] for i in range(3)],'loops':loops})
print(json.dumps(rows,indent=2))
(ROOT/'experiments/metahuman/clothing-audit.json').write_text(json.dumps(rows,indent=2))
