"""Write captured neck rotations into baked clips, bypassing rig constraints."""
import json, traceback
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman'
report=json.loads((OUT/'reactions-report.json').read_text())
report['status']='writing_direct_neck'
def save(): (OUT/'reactions-report.json').write_text(json.dumps(report,indent=2))
def mul(a,b):
    return unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,
                       a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,
                       a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,
                       a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z)
try:
    report.pop('error',None)
    save()
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    for take in report['reactions']:
        name=take['name'];count=take['source_frames']
        motion=unreal.load_asset('/Game/Audition/Baked/AS_RawMotion_'+name)
        values={a:[unreal.AnimationLibrary.get_float_value_at_time(motion,c,i/30) for i in range(count)] for a,c in [('roll','HeadRoll'),('pitch','HeadPitch'),('yaw','HeadYaw')]}
        smooth={a:[sum(v[max(0,min(count-1,i+d))]*w for d,w in [(-2,1),(-1,2),(0,3),(1,2),(2,1)])/9 for i in range(count)] for a,v in values.items()}
        path='/Game/Audition/Reactions/LS_Baked_'+name
        seq=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/Game/Audition/Sequences/LS_Closeup_'+name,path)
        for clip in take['clips']:
            anim=unreal.load_asset(clip['asset'])
            part=clip['part']
            mesh=unreal.load_asset('/Game/MetaHumans/AuditionMale/'+part+'/SKM_AuditionMale_'+part+'Mesh')
            anim.set_retarget_source_asset(mesh)
            source=unreal.load_asset('/Game/Audition/Sequences/LS_Closeup_'+name)
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(source)
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            binding_source=next(b for b in source.get_bindings() if str(b.get_display_name())==clip['part'])
            options=unreal.AnimSeqExportOption()
            options.export_transforms=True;options.export_attribute_curves=True;options.export_material_curves=True
            options.evaluate_all_skeletal_mesh_components=True;options.record_in_world_space=False
            options.delay_before_start=unreal.FrameNumber(8)
            options.use_custom_frame_rate=True;options.custom_frame_rate=unreal.FrameRate(30,1)
            options.use_custom_time_range=True;options.custom_start_frame=unreal.FrameNumber(0);options.custom_end_frame=unreal.FrameNumber(count-1);options.custom_display_rate=unreal.FrameRate(30,1)
            if not unreal.ControlRigSequencerLibrary.export_anim_sequence_from_sequencer(anim,options,binding_source,False):raise RuntimeError('Baseline bake failed')
            unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
            controller=anim.get_editor_property('controller')
            for bone,share in [('neck_01',.30),('neck_02',.30),('head',.40)]:
                rest=unreal.AnimationLibrary.get_bone_pose_for_frame(anim,bone,0,False)
                rotations=[]
                for i in range(count+1):
                    f=min(i,count-1)
                    delta=unreal.Rotator(pitch=smooth['pitch'][f]*share,yaw=smooth['yaw'][f]*share,roll=smooth['roll'][f]*share).quaternion()
                    rotations.append(mul(rest.rotation,delta))
                if not controller.set_bone_track_keys(bone,[rest.translation]*(count+1),rotations,[rest.scale3d]*(count+1),False):
                    raise RuntimeError('Failed bone keys '+bone)
            unreal.EditorAssetLibrary.save_loaded_asset(anim)
            binding=next(b for b in seq.get_bindings() if str(b.get_display_name())==clip['part'])
            for track in binding.get_tracks():
                if isinstance(track,(unreal.MovieSceneControlRigParameterTrack,unreal.MovieSceneSkeletalAnimationTrack)):
                    binding.remove_track(track)
            track=binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
            section=track.add_section();section.set_range(0,count)
            params=section.get_editor_property('params');params.animation=anim;params.force_custom_mode=True;section.set_editor_property('params',params)
            # The facial joints are already solved. A second post-process rig
            # would overwrite the baked pose when playing these AnimSequences.
            for old in binding.get_tracks():
                if isinstance(old,unreal.MovieSceneBoolTrack):binding.remove_track(old)
            disable=binding.add_track(unreal.MovieSceneBoolTrack)
            disable.set_property_name_and_path('bDisablePostProcessBlueprint','bDisablePostProcessBlueprint')
            disable_section=disable.add_section();disable_section.set_range(0,count)
            disable_section.get_all_channels()[0].set_default(clip['part']=='Face')
            task=unreal.AssetExportTask();task.object=anim;task.filename=str(OUT/'exports/reactions'/clip['file'])
            task.automated=True;task.prompt=False;task.replace_identical=True
            opts=unreal.FbxExportOption();opts.export_preview_mesh=False;opts.ascii=False;task.options=opts
            if not unreal.Exporter.run_asset_export_task(task): raise RuntimeError('FBX export failed')
            clip['bytes']=Path(task.filename).stat().st_size
        unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
        take['sequence']=seq.get_path_name()
        take['rotation_distribution']={'neck_01':.30,'neck_02':.30,'head':.40}
        take['neck_method']='Recorded rotation written to local bone keys after facial bake; playback bypasses Control Rig'
        save()
    report['status']='baked_and_exported'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    save()
