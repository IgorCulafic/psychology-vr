import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'man/source/dhana.gltf'))
arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
arm.animation_data_clear();arm.data.pose_position='REST'
report={'bones':[], 'meshes':[]}
for b in arm.data.bones:
    if any(x in b.name.lower() for x in ['head','eye','jaw','neck']):
        report['bones'].append({'name':b.name,'head':list(arm.matrix_world@b.head_local),'tail':list(arm.matrix_world@b.tail_local)})
for o in bpy.context.scene.objects:
    if o.type!='MESH':continue
    pts=[o.matrix_world@v.co for v in o.data.vertices]
    report['meshes'].append({'name':o.name,'materials':[m.name for m in o.data.materials], 'vertices':len(pts),
        'min':[min(p[i] for p in pts) for i in range(3)],'max':[max(p[i] for p in pts) for i in range(3)]})
    if any('Skin' in m.name or 'Eye' in m.name or 'Teeth' in m.name for m in o.data.materials):
        (ROOT/'.cache'/('face-'+o.name+'.json')).write_text(json.dumps({'vertices':[list(p) for p in pts], 'faces':[list(p.vertices) for p in o.data.polygons]}))
(ROOT/'docs/generated/face-source-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
head=next(b for b in arm.data.bones if b.name.endswith('mixamorig:Head'))
target=arm.matrix_world@head.head_local+Vector((0,-.025,.105))
bpy.ops.object.camera_add(location=target+Vector((0,-.8,.015)));cam=bpy.context.object
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.38
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Face audit');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
for offset,power in [((-.4,-.5,.5),35),((.4,-.25,.1),18)]:
    bpy.ops.object.light_add(type='AREA',location=target+Vector(offset));light=bpy.context.object;light.data.energy=power;light.data.shape='DISK';light.data.size=.7
    light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(ROOT/'docs/generated/alex-face-source.png');bpy.ops.render.render(write_still=True)
