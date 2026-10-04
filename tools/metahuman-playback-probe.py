import unreal,json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'experiments/metahuman/playback-probe.json'
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
seq=unreal.load_asset('/Game/Audition/Reactions/LS_Baked_crying')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(200)
unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
player,actor=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,unreal.MovieSceneSequencePlaybackSettings())
position=unreal.MovieSceneSequencePlaybackParams()
position.time=200/30;position.position_type=unreal.MovieScenePositionType.TIME
player.set_playback_position(position)
report=[]
for binding in seq.get_bindings():
    row={'name':str(binding.get_display_name()),'objects':[],'tracks':[]}
    report.append(row)
    out.write_text(json.dumps(report,indent=2))
    bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',binding.get_id())
    objects=player.get_bound_objects(bid)
    for o in objects:
        item={'class':o.get_class().get_name(),'path':o.get_path_name()}
        if isinstance(o,unreal.SkeletalMeshComponent):
            item['animation_mode']=str(o.get_editor_property('animation_mode'))
            item['anim_instance']=str(o.get_anim_instance())
            item['disable_post_process']=o.get_editor_property('disable_post_process_blueprint')
            item['head']=str(o.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_COMPONENT))
        row['objects'].append(item)
    for t in binding.get_tracks():
        tr={'class':t.get_class().get_name(),'sections':[]}
        for s in t.get_sections():
            se={}
            if s.has_start_frame():se['start']=s.get_start_frame()
            if s.has_end_frame():se['end']=s.get_end_frame()
            if isinstance(s,unreal.MovieSceneSkeletalAnimationSection):se['params']=str(s.get_editor_property('params'))
            tr['sections'].append(se)
        row['tracks'].append(tr)
    out.write_text(json.dumps(report,indent=2))
out.write_text(json.dumps(report,indent=2))
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
