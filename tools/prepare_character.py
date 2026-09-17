"""Run with Blender --background --python tools/prepare_character.py.

Preserves the original glTF; exports a working FBX and a visual audit.
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'unity/Assets/PsychologyVR/Art/Characters/Alex'
AUDIT = ROOT / 'docs/generated'
OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / 'man/source/dhana.gltf'))
armature = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
objects = [armature] + meshes
actions = list(bpy.data.actions)
sys.path.insert(0,str(ROOT/'tools'))
from alex_facial_shapes import add_facial_shapes
add_facial_shapes(meshes,AUDIT/'alex-facial-shapes.json')

def bounds():
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pts = [o.matrix_world @ Vector(p) for src in meshes for o in [src.evaluated_get(depsgraph)] for p in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]

report = {
    'source': 'man/source/dhana.gltf',
    'mesh_count': len(meshes),
    'bone_count': len(armature.data.bones),
    'shape_keys': {o.name: list(o.data.shape_keys.key_blocks.keys()) if o.data.shape_keys else [] for o in meshes},
    'actions': [{'name': a.name, 'frames': list(a.frame_range)} for a in actions],
    'bounds': bounds(),
}
for image in bpy.data.images:
    if image.type == 'IMAGE':
        path = OUT / (bpy.path.clean_name(image.name) + '.png')
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()

bpy.ops.object.select_all(action='DESELECT')
for obj in objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.export_scene.fbx(
    filepath=str(OUT / 'Alex.fbx'), use_selection=True,
    object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False,
    bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
    path_mode='COPY', embed_textures=True, axis_forward='-Z', axis_up='Y',
    use_mesh_modifiers=False,
)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.render.resolution_x = 800
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new('Audit world')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.16, 0.18, 0.21, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.5

def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

lo, hi = bounds()
height = max(hi[2] - lo[2], 1)
center = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
bpy.ops.object.camera_add(location=(center.x, center.y - height * 2.2, center.z + height * .1))
camera = bpy.context.object
aim(camera, center)
camera.data.type = 'ORTHO'
camera.data.ortho_scale = height * 1.3
scene.camera = camera
for name, offset, energy, size in [('Key', (-2, -3, 4), 650, 4), ('Fill', (2, -1, 2), 300, 3)]:
    bpy.ops.object.light_add(type='AREA', location=center + Vector(offset))
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = 'DISK'
    light.data.size = size
    aim(light, center)

sit = next((a for a in actions if a.name.lower().endswith('sit') or a.name.lower() == 'sit'), None)
if sit:
    armature.animation_data_create()
    armature.animation_data.action = sit
    if hasattr(sit, 'slots') and len(sit.slots):
        armature.animation_data.action_slot = sit.slots[0]
    report['seated_samples'] = []
    for label, fraction in [('start', 0), ('middle', .5), ('end', 1)]:
        frame = round(sit.frame_range[0] + (sit.frame_range[1] - sit.frame_range[0]) * fraction)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        report['seated_samples'].append({'label': label, 'frame': frame, 'bounds': bounds()})
        scene.render.filepath = str(AUDIT / f'alex-sit-{label}.png')
        bpy.ops.render.render(write_still=True)
else:
    scene.render.filepath = str(AUDIT / 'alex-audit.png')
    bpy.ops.render.render(write_still=True)
(AUDIT / 'character-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
