import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'man/source/dhana.gltf'))
arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
head=arm.pose.bones['mixamorig:Head']
rest=(arm.matrix_world@head.bone.matrix_local).to_quaternion()
local_forward=rest.inverted()@Vector((0,-1,0))
action=next(a for a in bpy.data.actions if a.name.lower().endswith('sit'))
arm.animation_data.action=action
if action.slots:arm.animation_data.action_slot=action.slots[0]
report=[]
mesh=bpy.data.objects['Object_11'];groups={g.index:g.name for g in mesh.vertex_groups};totals={}
for vertex in mesh.data.vertices:
    for group in vertex.groups:totals[groups[group.group]]=totals.get(groups[group.group],0)+group.weight
print('FACE_WEIGHTS',sorted(totals.items(),key=lambda v:-v[1])[:8])
for sec in [0,.5,1.2,2.4,3.5,5,6.8]:
    bpy.context.scene.frame_set(round(sec*30));bpy.context.view_layer.update()
    matrix=arm.matrix_world@head.matrix
    report.append({'second':sec,'forward':list(matrix.to_quaternion()@local_forward),'position':list(matrix.translation)})
(ROOT/'docs/generated/seated-gaze-audit.json').write_text(json.dumps(report,indent=2))
