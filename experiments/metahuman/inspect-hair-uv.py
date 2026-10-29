import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='D:/AI/Psychology_VR/experiments/metahuman/exports/unity/stefan/models/Hair_cards_0.fbx')
for o in bpy.data.objects:
 if o.type=='MESH':
  print(o.name,[(u.name,[(min(x.uv[a] for x in u.data),max(x.uv[a] for x in u.data)) for a in range(2)]) for u in o.data.uv_layers])
