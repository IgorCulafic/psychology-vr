"""Bake identity-specific raw reactions and normalized speech/expression poses."""
import bisect,json,sys,traceback,math,re
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/metahuman/exports/unity'
report={'status':'starting','characters':[]}
ONLY_POSES='-mhposes' in unreal.SystemLibrary.get_command_line().lower()
previous=json.loads((OUT/'performance.json').read_text()) if ONLY_POSES else None
only_match=re.search(r'-mhOnly=([\w-]+)',unreal.SystemLibrary.get_command_line(),re.I)
ONLY_CHARACTER=only_match.group(1).lower() if only_match else None
if ONLY_CHARACTER:
    previous=json.loads((OUT/'performance.json').read_text())
    report['characters']=[c for c in previous['characters'] if c['id']!=ONLY_CHARACTER]
def save(): (OUT/'performance.json').write_text(json.dumps(report,indent=2))
def both(control,value=1):return {'CTRL_'+side+'_'+control:value for side in ['L','R']}
poses=[('neutral',{}),('JawOpen',{'CTRL_C_jaw.Y':.8}),('MouthPucker',{**both('mouth_purseU',.85),**both('mouth_purseD',.85)}),('MouthWide',both('mouth_stretch',.7)),('MouthPress',{**both('mouth_lipsTogetherU',.8),**both('mouth_lipsTogetherD',.8)}),('MouthSmile',both('mouth_cornerPull',.85)),('MouthFrown',both('mouth_cornerDepress',.85)),('BrowWorry',{**both('brow_raiseIn',.8),**both('brow_down',.25)}),('BrowTense',both('brow_down',.85)),('BrowRaise',{**both('brow_raiseIn',.85),**both('brow_raiseOut',.85)}),('BlinkLeft',{'CTRL_L_eye_blink':1}),('BlinkRight',{'CTRL_R_eye_blink':1}),('EyeSquint',{**both('eye_squintInner',.8),**both('eye_cheekRaise',.6)}),('EyeLookLeft',{'CTRL_C_eye.X':-.7}),('EyeLookRight',{'CTRL_C_eye.X':.7}),('EyeLookUp',{'CTRL_C_eye.Y':.7}),('EyeLookDown',{'CTRL_C_eye.Y':-.7}),('BrowRaiseLeft',{'CTRL_L_brow_raiseIn':.8,'CTRL_L_brow_raiseOut':.8}),('EyeWide',both('eye_blink',-.55)),('NoseWrinkle',both('nose_wrinkleUpper',.8)),('UpperLipRaise',both('mouth_upperLipRaise',.8))]
poses=[(name,({**both('mouth_pressU',.8),**both('mouth_pressD',.8)} if name=='MouthPress' else {**both('nose.Y',.8),**both('nose_wrinkleUpper',.8)} if name=='NoseWrinkle' else values)) for name,values in poses]

def channels(seq):
    b=next(b for b in seq.get_bindings() if str(b.get_display_name())=='Face')
    return {str(c.get_editor_property('channel_name')):c for t in b.get_tracks() for s in t.get_sections() for c in s.get_all_channels() if any(k in c.get_class().get_name() for k in ['FloatChannel','DoubleChannel'])}
def sample(c):
    pairs=sorted((k.get_time().frame_number.value+float(k.get_time().sub_frame),float(k.get_value())) for k in c.get_keys())
    return ([p[0] for p in pairs],[p[1] for p in pairs],float(c.get_default() or 0))
def at(d,f):
    ts,vs,default=d
    if not ts:return default
    j=bisect.bisect_right(ts,f)
    if j==0:return vs[0]
    if j==len(ts):return vs[-1]
    k=(f-ts[j-1])/(ts[j]-ts[j-1]);return vs[j-1]*(1-k)+vs[j]*k
def mul(a,b):return unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z)
try:
    cast=json.loads((ROOT/'experiments/metahuman/cast.json').read_text())['characters']
    if ONLY_CHARACTER:cast=[c for c in cast if c['id']==ONLY_CHARACTER];assert cast,ONLY_CHARACTER
    takes=json.loads((ROOT/'experiments/metahuman/media/manifest.json').read_text())
    prepared=False
    for char in cast:
        key=char.get('animation_key',char['id']);base='/Game/Audition/Unity/'+key
        for mood in ['poses','afraid','crying','angry']:
            original='/Game/Audition/Sequences/LS_Closeup_afraid' if char['id']=='alex' else '/Game/Audition/Cast/'+key+'/afraid/LS_Control_emotion'
            path=base+'/LS_'+mood
            if not unreal.EditorAssetLibrary.does_asset_exist(path):
                obj=unreal.EditorAssetLibrary.duplicate_asset(original,path);assert obj,original
                assert unreal.EditorAssetLibrary.save_loaded_asset(obj,only_if_is_dirty=False);prepared=True
    if prepared:
        report['status']='prepared_restart_required';save();sys.exit(0)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    asset_tools=unreal.AssetToolsHelpers.get_asset_tools()
    for char in cast:
        name=char['asset_name'];base='/Game/Audition/Unity/'+char.get('animation_key',char['id']);row={'id':char['id'],'asset_name':name,'clips':[],'poses':[p[0] for p in poses]};report['characters'].append(row)
        mesh=unreal.load_asset(f'/Game/MetaHumans/{name}/Face/SKM_{name}_FaceMesh')
        for mood in ['poses','afraid','crying','angry']:
            if ONLY_POSES and mood!='poses':
                prior=next(c for c in previous['characters'] if c['id']==char['id'])
                row['clips'].append(next(c for c in prior['clips'] if c['name']==mood));continue
            report['status']='baking_'+char['id']+'_'+mood;save()
            seq=unreal.load_asset(base+'/LS_'+mood);target=channels(seq)
            assert len(target)>=200
            if mood=='poses':count=len(poses)
            else:
                take=next(t for t in takes if t['name']==mood);count=take['frames']
                source={n:sample(c) for n,c in channels(unreal.load_asset('/Game/Audition/Sequences/LS_Closeup_'+mood)).items()}
            for label,c in target.items():
                initial=at(sample(c),0)
                for key in c.get_keys():c.remove_key(key)
                for i in range(count):
                    if mood=='poses':
                        # Aim transform controls and rig switches are not normalized expressions.
                        preserve=any(t in label for t in ['Aim','Switch','FollowHead','followHead'])
                        value=initial if preserve else poses[i][1].get(label,0.)
                    else:value=at(source[label],i) if label in source else initial
                    c.add_key(unreal.FrameNumber(i),value,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            seq.set_playback_end(count);unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq);unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0);unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            path=base+'/AS_'+mood;anim=unreal.load_asset(path)
            if not anim:
                factory=unreal.AnimSequenceFactory();factory.target_skeleton=mesh.get_editor_property('skeleton');anim=asset_tools.create_asset('AS_'+mood,base,unreal.AnimSequence,factory)
            anim.set_retarget_source_asset(mesh)
            binding=next(b for b in seq.get_bindings() if str(b.get_display_name())=='Face')
            opts=unreal.AnimSeqExportOption();opts.export_transforms=True;opts.evaluate_all_skeletal_mesh_components=True;opts.record_in_world_space=False;opts.delay_before_start=unreal.FrameNumber(8);opts.use_custom_frame_rate=True;opts.custom_frame_rate=unreal.FrameRate(30,1);opts.use_custom_time_range=True;opts.custom_start_frame=unreal.FrameNumber(0);opts.custom_end_frame=unreal.FrameNumber(count-1);opts.custom_display_rate=unreal.FrameRate(30,1)
            assert unreal.ControlRigSequencerLibrary.export_anim_sequence_from_sequencer(anim,opts,binding,False)
            if mood!='poses':
                motion=unreal.load_asset('/Game/Audition/Baked/AS_RawMotion_'+mood)
                raw={a:[unreal.AnimationLibrary.get_float_value_at_time(motion,c,i/30) for i in range(count)] for a,c in [('roll','HeadRoll'),('pitch','HeadPitch'),('yaw','HeadYaw')]}
                smooth={a:[sum(v[max(0,min(count-1,i+d))]*w for d,w in [(-2,1),(-1,2),(0,3),(1,2),(2,1)])/9 for i in range(count)] for a,v in raw.items()}
                controller=anim.get_editor_property('controller')
                for bone,share in [('neck_01',.3),('neck_02',.3),('head',.4)]:
                    rest=unreal.AnimationLibrary.get_bone_pose_for_frame(anim,bone,0,False)
                    rots=[mul(rest.rotation,unreal.Rotator(pitch=smooth['pitch'][min(i,count-1)]*share,yaw=smooth['yaw'][min(i,count-1)]*share,roll=smooth['roll'][min(i,count-1)]*share).quaternion()) for i in range(count+1)]
                    assert controller.set_bone_track_keys(bone,[rest.translation]*(count+1),rots,[rest.scale3d]*(count+1),False)
            anim.set_retarget_source_asset(mesh);unreal.EditorAssetLibrary.save_loaded_asset(anim,only_if_is_dirty=False)
            file=OUT/char['id']/'animations'/('runtime_'+mood+'.fbx');file.parent.mkdir(exist_ok=True,parents=True)
            task=unreal.AssetExportTask();task.object=anim;task.filename=str(file);task.automated=True;task.prompt=False;task.replace_identical=True
            options=unreal.FbxExportOption();options.ascii=False;options.export_preview_mesh=False;task.options=options;assert unreal.Exporter.run_asset_export_task(task)
            row['clips'].append({'name':mood,'file':str(file.relative_to(OUT)).replace('\\','/'),'frames':count});save()
            unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    report['status']='exported'
except Exception:report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:save();unreal.SystemLibrary.quit_editor()
