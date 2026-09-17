import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(R/'jumper_man/source/Ex wife\'s new husband.fbx'))
a=next(o for o in bpy.data.objects if o.type=='ARMATURE')
a.animation_data_clear()
for p in a.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update()
r={}
for side in ['L','R']:
 r[side]=[]
 for name in ['Hand']+[f'{d}{j}' for d in ['Index','Mid','Ring','Pinky','Thumb'] for j in [1,2,3]]:
  b=a.pose.bones['CC_Base_'+side+'_'+name]
  r[side].append({'bone':name,'parent':b.parent.name,'head':list(a.matrix_world@b.head),'tail':list(a.matrix_world@b.tail),'x':list((a.matrix_world@b.matrix).to_3x3().col[0]),'y':list((a.matrix_world@b.matrix).to_3x3().col[1])})
(R/'docs/generated/jumper-hand-rig.json').write_text(json.dumps(r,indent=2))
print('HAND_RIG_AUDIT_OK')
