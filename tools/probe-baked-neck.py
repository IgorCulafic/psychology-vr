import bpy, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'experiments/metahuman'
out={}
for part in ['face','body']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(root/'exports/reactions'/('crying_'+part+'.fbx')))
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    out[part]={}
    for frame in [1,100,200,300,400,500]:
        bpy.context.scene.frame_set(frame)
        out[part][frame]={n:{'local':list(arm.pose.bones[n].rotation_quaternion),'global':list(arm.pose.bones[n].matrix.to_quaternion())} for n in ['neck_01','neck_02','head']}
(root/'baked-neck-probe.json').write_text(json.dumps(out,indent=2))
