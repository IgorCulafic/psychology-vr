"""Bake head-following tear projectors into an isolated crying sequence."""
import json,traceback,runpy
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/metahuman/tears';OUT.mkdir(exist_ok=True)
report={'status':'starting','sequences':[]}
def mul(a,b):
    return unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z)
try:
    mat=runpy.run_path(str(ROOT/'tools/metahuman-tear-material.py'))['make_tear_material']()
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    source=unreal.load_asset('/Game/Audition/Speaking/crying/LS_emotion')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    player,player_actor=unreal.LevelSequencePlayer.create_level_sequence_player(world,source,unreal.MovieSceneSequencePlaybackSettings())
    pos=unreal.MovieSceneSequencePlaybackParams();pos.time=0;pos.position_type=unreal.MovieScenePositionType.TIME;player.set_playback_position(pos)
    b=next(b for b in source.get_bindings() if str(b.get_display_name())=='Face')
    bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',b.get_id())
    face=next(o for o in player.get_bound_objects(bid) if isinstance(o,unreal.SkeletalMeshComponent))
    head0=face.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_WORLD)
    anim=unreal.load_asset('/Game/Audition/Speaking/crying/AS_emotion_Face')
    chain=['head']
    while str(face.get_parent_bone(chain[-1])) not in ['None','']:
        chain.append(str(face.get_parent_bone(chain[-1])))
    def local_head(frame):
        result=unreal.Transform()
        for bone in chain:
            local=unreal.AnimationLibrary.get_bone_pose_for_frame(anim,bone,frame,False)
            result=unreal.MathLibrary.compose_transforms(result,local)
        return result
    component=unreal.MathLibrary.compose_transforms(unreal.MathLibrary.invert_transform(local_head(0)),head0)
    heads=[unreal.MathLibrary.compose_transforms(local_head(i),component) for i in range(257)]
    report['head_chain']=chain
    report['head_positions']=[[t.translation.x,t.translation.y,t.translation.z] for t in heads]
    report['head_rotations']=[[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w] for t in heads]
    path='/Game/Audition/Tears/LS_CryingTears'
    seq=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset(source.get_path_name(),path)
    seq.modify()
    for binding in list(seq.get_bindings()):
        if str(binding.get_display_name()).startswith('Tear'):binding.remove()
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    report['projectors']=[]
    for side,phase in [('L',0.),('R',.47)]:
        eye=face.get_socket_transform('FACIAL_'+side+'_EyelidLowerB2',unreal.RelativeTransformSpace.RTS_WORLD).translation
        center=unreal.Vector(eye.x-1.,eye.y+(.15 if side=='L' else -.15),eye.z-3.1)
        local_center=unreal.MathLibrary.inverse_transform_location(head0,center)
        # UE decal tangent +Z becomes local -X; keep it facing the front of
        # this character (-world X), rather than shading the film backwards.
        base_rotation=unreal.Rotator(0,0,0).quaternion()
        inv=unreal.Quat(-head0.rotation.x,-head0.rotation.y,-head0.rotation.z,head0.rotation.w)
        local_rotation=mul(inv,base_rotation)
        actor=actors.spawn_actor_from_class(unreal.DecalActor,center,base_rotation.rotator())
        actor.set_actor_label('Tear_'+side)
        comp=actor.get_component_by_class(unreal.DecalComponent);comp.set_decal_material(mat)
        comp.set_editor_property('decal_size',unreal.Vector(4.,1.2,3.))
        comp.set_editor_property('fade_screen_size',0.)
        binding=seq.add_spawnable_from_instance(actor);binding.set_display_name('Tear_'+side)
        section=binding.add_track(unreal.MovieScene3DTransformTrack).add_section();section.set_range(0,257)
        channels=section.get_all_channels()
        for i,t in enumerate(heads):
            point=unreal.MathLibrary.transform_location(t,local_center);rot=mul(t.rotation,local_rotation).rotator()
            values=[point.x,point.y,point.z,rot.roll,rot.pitch,rot.yaw,1.,1.,1.]
            for channel,value in zip(channels,values):channel.add_key(unreal.FrameNumber(i),value,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        component_binding=seq.add_possessable(comp);component_binding.set_parent(binding);component_binding.set_display_name('TearMaterial_'+side)
        track=component_binding.add_track(unreal.MovieSceneComponentMaterialTrack)
        info=unreal.ComponentMaterialInfo();info.material_type=unreal.ComponentMaterialType.DECAL_MATERIAL
        track.set_material_info(info)
        section=track.add_section();section.set_range(0,257)
        wet_parameter=unreal.MaterialParameterInfo();wet_parameter.set_editor_property('name','Wetness')
        phase_parameter=unreal.MaterialParameterInfo();phase_parameter.set_editor_property('name','Phase')
        tick_rate=seq.get_tick_resolution()
        # Material section keys use raw sequence ticks, unlike scripting
        # transform channels which accept display frames by default.
        for frame,value in [(0,0.),(40,.9),(220,.9),(256,0.)]:
            ticks=round(frame*tick_rate.numerator/(30*tick_rate.denominator))
            section.add_scalar_parameter_key(wet_parameter,unreal.FrameNumber(ticks),value,'','')
        section.add_scalar_parameter_key(phase_parameter,unreal.FrameNumber(0),phase,'','')
        actors.destroy_actor(actor)
        report['projectors'].append({'side':side,'eye':[eye.x,eye.y,eye.z],'center':[center.x,center.y,center.z]})
    unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
    player.stop();actors.destroy_actor(player_actor)
    report['sequences']=[{'name':'crying-tears','asset':seq.get_path_name(),'frames':257}]
    report['status']='exported_not_rendered'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    (OUT/'build-report.json').write_text(json.dumps(report,indent=2))
    unreal.SystemLibrary.quit_editor()
