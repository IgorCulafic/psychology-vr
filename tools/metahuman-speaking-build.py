"""Blend captured upper-face acting with speech controls, then bake playback."""
import bisect,json,traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
ANGER='-mhangerblend' in unreal.SystemLibrary.get_command_line().lower()
CAST='-mhcast' in unreal.SystemLibrary.get_command_line().lower()
OUT=ROOT/'experiments/metahuman'/('cast' if CAST else ('anger-blend' if ANGER else 'speaking'))
report={'status':'building','sequences':[]}
def save(): (OUT/'build-report.json').write_text(json.dumps(report,indent=2))
def channels(seq):
    binding=next(b for b in seq.get_bindings() if str(b.get_display_name())=='Face')
    return {str(c.get_editor_property('channel_name')):c for t in binding.get_tracks() for s in t.get_sections() for c in s.get_all_channels() if any(k in c.get_class().get_name() for k in ['FloatChannel','DoubleChannel'])}
def sampler(channel):
    keys=channel.get_keys()
    pairs=sorted((k.get_time().frame_number.value+float(k.get_time().sub_frame),float(k.get_value())) for k in keys)
    default=channel.get_default()
    return ([p[0] for p in pairs],[p[1] for p in pairs],float(default) if default is not None else 0.)
def at(data,time):
    times,values,default=data
    if not times:return default
    i=bisect.bisect_right(times,time)
    if i==0:return values[0]
    if i==len(times):return values[-1]
    f=(time-times[i-1])/(times[i]-times[i-1])
    return values[i-1]*(1-f)+values[i]*f
def upper(name):
    n=name.lower()
    return any(x in n for x in ['_brow','_eyelid','_eye_blink','_eye_squint','_eye_widen','_eye_cheek','_nose'])
def mul(a,b):
    return unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z)
def ramp(lo,hi,value):
    t=max(0.,min(1.,(value-lo)/(hi-lo)))
    return t*t*(3-2*t)
def anger_mouth(label,speech_value,recorded_value,gate,variant):
    jaw_weight,lip_weight=(.40,.28) if variant=='balanced' else (.78,.60)
    if label=='CTRL_C_jaw.Y':weight=jaw_weight
    elif any(k in label for k in ['upperLipRaise','lowerLipDepress','mouth_stretch','sharpCornerPull']) and 'Close' not in label:weight=lip_weight
    elif label=='CTRL_C_jaw_openExtreme':weight=lip_weight*.3
    else:return speech_value
    return min(1.,speech_value+weight*gate*max(0.,recorded_value-speech_value))
try:
    assert json.loads((ROOT/'experiments/metahuman/speaking/solve-report.json').read_text())['status']=='solved_restart_before_blend'
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    assets=unreal.AssetToolsHelpers.get_asset_tools()
    for take in json.loads((OUT/'manifest.json').read_text(encoding='utf-8')):
        name=take['name'];count=take['frames'];package=take['package'] if CAST else ('/Game/Audition/AngerBlend' if ANGER else '/Game/Audition/Speaking/'+name)
        angry_blend=ANGER or (CAST and name=='angry')
        identity=take['character']['asset_name'] if CAST else 'AuditionMale'
        speech=unreal.load_asset('/Game/Audition/Speaking/'+name+'/LS_Audio')
        source=unreal.load_asset('/Game/Audition/Sequences/LS_Closeup_'+name)
        audio_data={n:sampler(c) for n,c in channels(speech).items()}
        emotion_data={n:sampler(c) for n,c in channels(source).items()}
        gates=[]
        for i in range(count):
            jaw=at(audio_data['CTRL_C_jaw.Y'],i)
            closure=max([at(v,i) for n,v in audio_data.items() if any(k in n for k in ['lipsTogether','lipsPress','stretchLipsClose'])]+[0.])
            rounding=max([at(v,i) for n,v in audio_data.items() if any(k in n for k in ['mouth_funnel','mouth_purse'])]+[0.])
            gates.append(ramp(.07,.24,jaw)*(1-ramp(.40,.85,closure))*(1-.65*ramp(.35,.85,rounding)))
        report['channel_names']=list(audio_data);save()
        selected=[n for n in audio_data if upper(n)]
        if len(selected)<6:raise RuntimeError('Upper face mapping too small: '+str(selected))
        motion=unreal.load_asset('/Game/Audition/Baked/AS_RawMotion_'+name)
        raw={axis:[unreal.AnimationLibrary.get_float_value_at_time(motion,curve,min(take['reaction_frames']-1,take['reaction_start_frame']+i)/30) for i in range(count)] for axis,curve in [('roll','HeadRoll'),('pitch','HeadPitch'),('yaw','HeadYaw')]}
        smooth={axis:[sum(v[max(0,min(count-1,i+d))]*w for d,w in [(-2,1),(-1,2),(0,3),(1,2),(2,1)])/9 for i in range(count)] for axis,v in raw.items()}
        for variant in (['shout' if angry_blend else 'emotion'] if CAST else (['balanced','shout'] if ANGER else ['lips','emotion'])):
            report['status']='building_'+name+'_'+variant;save()
            seq=unreal.load_asset(package+'/LS_Control_'+variant)
            seq.modify();seq.set_playback_end(count)
            target=channels(seq)
            if len(target)<100:raise RuntimeError('Need fresh editable sequence for '+name+' '+variant)
            matched=0;changed=[];mouth_difference=0.;closure_difference=0.;mouth_channels=[];jaw_values=[]
            for label,channel in target.items():
                if label not in audio_data:continue
                matched+=1
                for key in channel.get_keys():channel.remove_key(key)
                for i in range(count):
                    value=at(audio_data[label],i)
                    if variant!='lips' and upper(label) and label in emotion_data:
                        weight=take['upper_face_weight']
                        value=(1-weight)*value+weight*at(emotion_data[label],take['reaction_start_frame']+i)
                    elif angry_blend and label in emotion_data:
                        original=value
                        value=anger_mouth(label,value,at(emotion_data[label],take['reaction_start_frame']+i),gates[i],variant)
                        mouth_difference=max(mouth_difference,abs(value-original))
                        if gates[i]==0:closure_difference=max(closure_difference,abs(value-original))
                        if value!=original and label not in mouth_channels:mouth_channels.append(label)
                    elif any(x in label.lower() for x in ['mouth','jaw','lip','tongue']):
                        mouth_difference=max(mouth_difference,abs(value-at(audio_data[label],i)))
                    if label=='CTRL_C_jaw.Y':jaw_values.append(value)
                    channel.add_key(unreal.FrameNumber(i),value,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
                if variant!='lips' and upper(label):changed.append(label)
            if matched<100 or (not angry_blend and mouth_difference!=0) or closure_difference!=0:raise RuntimeError('Speech mapping validation failed')
            if angry_blend and mouth_difference<.05:raise RuntimeError('Anger mouth blend too weak')
            for t in seq.get_tracks():
                if isinstance(t,unreal.MovieSceneCameraCutTrack):
                    for s in t.get_sections():s.set_range(0,count)
            unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            clips=[]
            for part in ['Face','Body']:
                mesh=unreal.load_asset('/Game/MetaHumans/'+identity+'/'+part+'/SKM_'+identity+'_'+part+'Mesh')
                anim_name='AS_'+variant+'_'+part;anim=unreal.load_asset(package+'/'+anim_name)
                if not anim:
                    factory=unreal.AnimSequenceFactory();factory.target_skeleton=mesh.get_editor_property('skeleton')
                    anim=assets.create_asset(anim_name,package,unreal.AnimSequence,factory)
                anim.set_retarget_source_asset(mesh)
                binding=next(b for b in seq.get_bindings() if str(b.get_display_name())==part)
                options=unreal.AnimSeqExportOption();options.export_transforms=True;options.export_attribute_curves=True;options.export_material_curves=True
                options.evaluate_all_skeletal_mesh_components=True;options.record_in_world_space=False;options.delay_before_start=unreal.FrameNumber(8)
                options.use_custom_frame_rate=True;options.custom_frame_rate=unreal.FrameRate(30,1)
                options.use_custom_time_range=True;options.custom_start_frame=unreal.FrameNumber(0);options.custom_end_frame=unreal.FrameNumber(count-1);options.custom_display_rate=unreal.FrameRate(30,1)
                if not unreal.ControlRigSequencerLibrary.export_anim_sequence_from_sequencer(anim,options,binding,False):raise RuntimeError('Speech bake failed')
                if variant!='lips':
                    controller=anim.get_editor_property('controller')
                    for bone,share in [('neck_01',.3),('neck_02',.3),('head',.4)]:
                        rest=unreal.AnimationLibrary.get_bone_pose_for_frame(anim,bone,0,False)
                        rotations=[mul(rest.rotation,unreal.Rotator(pitch=smooth['pitch'][min(i,count-1)]*share,yaw=smooth['yaw'][min(i,count-1)]*share,roll=smooth['roll'][min(i,count-1)]*share).quaternion()) for i in range(count+1)]
                        if not controller.set_bone_track_keys(bone,[rest.translation]*(count+1),rotations,[rest.scale3d]*(count+1),False):raise RuntimeError('Neck write failed')
                anim.set_retarget_source_asset(mesh)
                unreal.EditorAssetLibrary.save_loaded_asset(anim,only_if_is_dirty=False)
                clips.append((part,anim))
            unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
            # Retain editable controls so another bake never consumes its own
            # previous animation output as the source.
            seq=unreal.load_asset(package+'/LS_'+variant)
            seq.modify();seq.set_playback_end(count)
            for part,anim in clips:
                binding=next(b for b in seq.get_bindings() if str(b.get_display_name())==part)
                for track in binding.get_tracks():
                    if isinstance(track,(unreal.MovieSceneControlRigParameterTrack,unreal.MovieSceneSkeletalAnimationTrack,unreal.MovieSceneBoolTrack)):binding.remove_track(track)
                s=binding.add_track(unreal.MovieSceneSkeletalAnimationTrack).add_section();s.set_range(0,count)
                p=s.get_editor_property('params');p.animation=anim;p.force_custom_mode=True;s.set_editor_property('params',p)
                track=binding.add_track(unreal.MovieSceneBoolTrack);track.set_property_name_and_path('bDisablePostProcessBlueprint','bDisablePostProcessBlueprint')
                s=track.add_section();s.set_range(0,count);s.get_all_channels()[0].set_default(part=='Face')
            unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
            report['sequences'].append({'name':(take['character']['id']+'-' if CAST else '')+name+'-'+variant,'identity':identity,'emotion':name,'variant':variant,'asset':seq.get_path_name(),'frames':count,'mapped_channels':matched,'upper_face_channels':changed,'mouth_control_difference':mouth_difference,'closure_frame_difference':closure_difference,'mouth_channels':mouth_channels,'jaw_range':[min(jaw_values),max(jaw_values)],'gated_closed_frames':sum(g==0 for g in gates),'baked_assets':[a.get_path_name() for _,a in clips]});save()
    report['status']='exported_not_rendered'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    save()
    if CAST:unreal.SystemLibrary.quit_editor()
