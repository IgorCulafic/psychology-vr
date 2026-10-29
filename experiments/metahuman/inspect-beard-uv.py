import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='D:/AI/Psychology_VR/experiments/metahuman/exports/unity/nikola/models/Beard_cards_0.fbx')
for o in bpy.data.objects:
 if o.type=='MESH':print(o.name,[u.name for u in o.data.uv_layers])
