import bpy
from collections import defaultdict
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='D:/AI/Psychology_VR/experiments/metahuman/exports/unity/ivan/models/Face.fbx')
for o in bpy.data.objects:
 if o.type!='MESH':continue
 for i,m in enumerate(o.data.materials):
  ps=[p for p in o.data.polygons if p.material_index==i];vs=set(v for p in ps for v in p.vertices)
  if vs:print(i,m.name,len(ps),'bounds',[(round(min(o.data.vertices[v].co[a] for v in vs),4),round(max(o.data.vertices[v].co[a] for v in vs),4)) for a in range(3)])
