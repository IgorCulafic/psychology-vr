"""Read back exported FBX data in Blender; never modifies source assets."""
import bpy
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman/exports/reactions'
report=[]
for path in sorted(OUT.glob('*.fbx')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    item={'file':path.name,'meshes':[],'armatures':[],'actions':[]}
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH':
            item['meshes'].append({'name':obj.name,'vertices':len(obj.data.vertices),
                'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons),
                'morph_targets':len(obj.data.shape_keys.key_blocks)-1 if obj.data.shape_keys else 0})
        elif obj.type=='ARMATURE':
            item['armatures'].append({'name':obj.name,'bones':len(obj.data.bones)})
    for action in bpy.data.actions:
        channels=[]
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    channels.extend(bag.fcurves)
        animated=[c for c in channels if c.keyframe_points and max(k.co.y for k in c.keyframe_points)-min(k.co.y for k in c.keyframe_points)>1e-5]
        item['actions'].append({'name':action.name,'frame_range':list(action.frame_range),'channels':len(channels),
            'varying_channels':len(animated),'varying_neck_channels':[c.data_path for c in animated if any('"'+n+'"' in c.data_path for n in ['neck_01','neck_02','head'])]})
    if item['actions']:
        arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        start,end=item['actions'][0]['frame_range']
        orientations=[]
        for frame in range(int(start),int(end)+1,10):
            bpy.context.scene.frame_set(frame)
            orientations.append(arm.pose.bones['head'].matrix.to_quaternion())
        item['head_global_rotation_degrees']=max(math.degrees(orientations[0].rotation_difference(q).angle) for q in orientations)
    report.append(item)
    print('FBX_AUDIT',path.name,flush=True)
(OUT/'fbx-validation.json').write_text(json.dumps(report,indent=2))
for item in report:
    if item['actions'] and item.get('head_global_rotation_degrees',0)<1:
        raise RuntimeError('Head orientation is static in '+item['file'])
