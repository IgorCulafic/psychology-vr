"""Give each cast identity consistent face framing, independent of body height."""
import json,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]/'experiments/metahuman';report={}
try:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    heights={}
    rows=json.loads((ROOT/'cast/build-report.json').read_text())['sequences']
    for row in rows:
        seq=unreal.load_asset(row['asset']);identity=row['identity']
        if identity not in heights:
            player,actor=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,unreal.MovieSceneSequencePlaybackSettings())
            pos=unreal.MovieSceneSequencePlaybackParams();pos.time=0;pos.position_type=unreal.MovieScenePositionType.TIME;player.set_playback_position(pos)
            b=next(b for b in seq.get_bindings() if str(b.get_display_name())=='Face')
            bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',b.get_id())
            face=next(o for o in player.get_bound_objects(bid) if isinstance(o,unreal.SkeletalMeshComponent))
            eyes=[face.get_socket_transform('FACIAL_'+s+'_EyelidLowerB2',unreal.RelativeTransformSpace.RTS_WORLD).translation.z for s in ['L','R']]
            heights[identity]=sum(eyes)/2-1.8
            player.stop();actors.destroy_actor(actor)
        for binding in seq.get_bindings():
            template=binding.get_object_template()
            if isinstance(template,unreal.CineCameraActor):
                template.modify();template.set_actor_location(unreal.Vector(-90,0,heights[identity]),False,False)
                for track in list(binding.get_tracks()):
                    if isinstance(track,unreal.MovieScene3DTransformTrack):binding.remove_track(track)
                section=binding.add_track(unreal.MovieScene3DTransformTrack).add_section()
                section.set_range(0,row['frames'])
                for channel,value in zip(section.get_all_channels(),[-90.,0.,heights[identity],0.,0.,0.,1.,1.,1.]):
                    channel.set_default(value)
                seq.modify()
        unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
    report={'status':'framed','camera_heights':heights}
except Exception:report={'status':'error','error':traceback.format_exc()}
(ROOT/'cast/framing-report.json').write_text(json.dumps(report,indent=2))
unreal.SystemLibrary.quit_editor()
