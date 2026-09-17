import bpy, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(root/'jumper_man/source/Ex wife\'s new husband.fbx'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
names=['Clavicle','Upperarm','UpperarmTwist01','UpperarmTwist02','Forearm','ForearmTwist01','ForearmTwist02','ElbowShareBone','Hand']
report=[{'bone':b.name,'parent':b.parent.name if b.parent else None,'head':list(arm.matrix_world@b.head_local)} for side in ['L','R'] for name in names if (b:=arm.data.bones.get('CC_Base_'+side+'_'+name))]
(root/'docs/generated/arm-joint-rig.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
