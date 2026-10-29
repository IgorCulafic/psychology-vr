import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='D:/AI/Psychology_VR/experiments/metahuman/exports/unity/ivan/models/Face.fbx')
o=next(o for o in bpy.data.objects if o.type=='MESH')
print('UVS',[u.name for u in o.data.uv_layers])
pts=[]
for p in o.data.polygons:
 if p.material_index==3:
  for li in p.loop_indices:
   v=o.data.vertices[o.data.loops[li].vertex_index]
   pts.append((tuple(v.co),tuple(o.data.uv_layers[0].data[li].uv)))
for pos,uv in sorted(set(pts),key=lambda x:x[0][1])[:25]:print([round(x,4) for x in pos],[round(x,4) for x in uv])
