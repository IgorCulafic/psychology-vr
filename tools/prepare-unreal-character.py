"""Run with Blender --background --python: export a seated idle without changing Unity assets."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/unreal'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT / 'unity/Assets/PsychologyVR/Art/Characters/Candidates/Jumper/Jumper.fbx'))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
# Start a fresh action: imported keys between our sampled frames must not leak
# standing/source poses into the seated idle.
for obj in bpy.data.objects:
    obj.animation_data_clear()
    if obj.type=='MESH' and obj.data.shape_keys: obj.data.shape_keys.animation_data_clear()
up = Vector((0, 0, 1)); forward = Vector((0, -1, 0))
def bone(name): return arm.pose.bones['CC_Base_' + name]
def update(): bpy.context.view_layer.update()
def matrix(b): return arm.matrix_world @ b.matrix
def position(b): return matrix(b).translation.copy()
def rotate(b, q):
    m = matrix(b); location, rotation, scale = m.decompose()
    b.matrix = arm.matrix_world.inverted() @ Matrix.LocRotScale(location, Quaternion(q) @ rotation, scale)
    update()
def aim(b, child, direction): rotate(b, (position(child)-position(b)).rotation_difference(direction))

update()
hip = bone('Hip'); m = matrix(hip); m.translation += up * (.57 - m.translation.z)
hip.matrix = arm.matrix_world.inverted() @ m; update()
for side in ['L', 'R']:
    thigh, calf, foot = [bone(side + '_' + x) for x in ['Thigh', 'Calf', 'Foot']]
    foot_rotation = matrix(foot).to_quaternion()
    aim(thigh, calf, forward - up * .12); aim(calf, foot, -up)
    rotate(foot, foot_rotation @ matrix(foot).to_quaternion().inverted())
    upper, fore, hand = [bone(side + '_' + x) for x in ['Upperarm', 'Forearm', 'Hand']]
    sign = 1 if position(upper).x > 0 else -1
    aim(upper, fore, Vector((sign * .27, -.07, .85)) - position(upper))
    aim(fore, hand, Vector((sign * .18, -.30, .73)) - position(fore))
    middle, index, pinky = [bone(side + '_' + x) for x in ['Mid1', 'Index1', 'Pinky1']]
    finger = (position(middle)-position(hand)).normalized()
    normal = (position(index)-position(hand)).cross(position(pinky)-position(hand)).normalized()
    if normal.dot(forward)<0: normal=-normal
    q = finger.rotation_difference(forward)
    n = q @ normal; n = (n - forward * n.dot(forward)).normalized()
    twist = math.atan2(forward.dot(n.cross(-up)), n.dot(-up))
    rotate(hand, Quaternion(forward, twist) @ q)

rest = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
scene = bpy.context.scene; scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 121
for frame in range(1, 122, 4):
    scene.frame_set(frame)
    phase = 2 * math.pi * (frame-1) / 120
    for b in arm.pose.bones:
        b.rotation_mode = 'QUATERNION'
        b.matrix_basis = rest[b.name]
        if b.name == 'CC_Base_Spine01': b.rotation_quaternion @= Quaternion((1,0,0), .012 * math.sin(phase))
        if b.name == 'CC_Base_Head': b.rotation_quaternion @= Quaternion((0,1,0), .009 * math.sin(phase))
        b.keyframe_insert('location', frame=frame)
        b.keyframe_insert('rotation_quaternion', frame=frame)
        b.keyframe_insert('scale', frame=frame)
if arm.animation_data and arm.animation_data.action: arm.animation_data.action.name = 'SeatedIdle'
scene.frame_set(1); update()
bpy.ops.export_scene.fbx(filepath=str(OUT / 'JumperSeated.fbx'), use_selection=False,
    object_types={'ARMATURE','MESH'}, add_leaf_bones=False, bake_anim=True,
    bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
    bake_anim_simplify_factor=0, axis_forward='-Y', axis_up='Z')
report = {'hip_m': list(position(hip)), 'bones': len(arm.pose.bones),
    'shape_keys': sum(len(o.data.shape_keys.key_blocks)-1 for o in bpy.data.objects if o.type=='MESH' and o.data.shape_keys),
    'output': str(OUT / 'JumperSeated.fbx')}
(OUT / 'character-export.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('UNREAL_CHARACTER_EXPORTED', json.dumps(report))
