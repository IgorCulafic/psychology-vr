import runpy,sys,bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
runpy.run_path(str(ROOT/'tools/audit-face.py'))
from alex_facial_shapes import add_facial_shapes
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials]
add_facial_shapes(meshes,ROOT/'docs/generated/alex-facial-shapes.json')
scene=bpy.context.scene;scene.cycles.samples=16;scene.render.resolution_x=630;scene.render.resolution_y=700
poses={'blink':{'BlinkLeft':1,'BlinkRight':1},'speech':{'JawOpen':.85},'rounded':{'JawOpen':.35,'MouthPucker':.8},
       'sad':{'BrowWorry':.9,'MouthFrown':.7,'EyeSquint':.3},'relieved':{'MouthSmile':.65,'BrowRaise':.15},
       'tense':{'BrowTense':.8,'MouthPress':.45,'EyeSquint':.4}}
for label,weights in poses.items():
    for o in meshes:
        if o.data.shape_keys:
            for key in o.data.shape_keys.key_blocks:key.value=weights.get(key.name,0)
    scene.render.filepath=str(ROOT/'docs/generated'/('alex-face-'+label+'.png'));bpy.ops.render.render(write_still=True)
print('FACIAL_SHAPES_PREVIEW_OK')
