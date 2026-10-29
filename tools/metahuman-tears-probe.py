"""Read surface landmark bones for a native decal tear audition."""
import json,traceback
from pathlib import Path
import unreal
OUT=Path(__file__).resolve().parents[1]/'experiments/metahuman/tears';OUT.mkdir(exist_ok=True)
r={}
try:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    seq=unreal.load_asset('/Game/Audition/Speaking/crying/LS_emotion')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    player,actor=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,unreal.MovieSceneSequencePlaybackSettings())
    pos=unreal.MovieSceneSequencePlaybackParams();pos.position_type=unreal.MovieScenePositionType.TIME;pos.time=0;player.set_playback_position(pos)
    b=next(b for b in seq.get_bindings() if str(b.get_display_name())=='Face')
    bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',b.get_id())
    face=next(o for o in player.get_bound_objects(bid) if isinstance(o,unreal.SkeletalMeshComponent))
    r['component_head']=str(face.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_WORLD))
    r['bones']={str(b):str(face.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in [face.get_bone_name(i) for i in range(face.get_num_bones())] if any(k in str(b).lower() for k in ['eyelid','cheek','head','eye'])}
    r['samples']=[]
    for frame in range(257):
        pos.time=frame/30;player.set_playback_position(pos)
        t=face.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_WORLD)
        r['samples'].append({'position':[t.translation.x,t.translation.y,t.translation.z],'rotation':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]})
    r['material_library']=[n for n in dir(unreal.MaterialEditingLibrary) if 'connect' in n]
    r['decal_material_doc']=unreal.DecalComponent.__doc__
    player.stop();unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
except Exception:r['error']=traceback.format_exc()
(OUT/'probe.json').write_text(json.dumps(r,indent=2))
unreal.SystemLibrary.quit_editor()
