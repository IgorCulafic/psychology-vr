"""Create neck-enabled reaction sequences and bake evaluated joints/morphs."""
import json
from pathlib import Path
import traceback
import re
import sys
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/metahuman'
FILES=OUT/'exports/reactions'
FILES.mkdir(parents=True,exist_ok=True)
report={'status':'starting','reactions':[],'model_files':[]}
tools=unreal.AssetToolsHelpers.get_asset_tools()

def save():
    (OUT/'reactions-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

def fbx(obj,filename,preview=False):
    task=unreal.AssetExportTask()
    task.object=obj
    task.filename=str(FILES/filename)
    task.automated=True
    task.prompt=False
    task.replace_identical=True
    options=unreal.FbxExportOption()
    options.ascii=False
    options.level_of_detail=False
    options.collision=False
    options.export_morph_targets=True
    options.export_preview_mesh=preview
    task.options=options
    if not unreal.Exporter.run_asset_export_task(task):
        raise RuntimeError('FBX export failed: '+filename+' '+str(task.errors))
    if not (FILES/filename).is_file():raise RuntimeError('FBX missing: '+filename)
    return {'file':filename,'bytes':(FILES/filename).stat().st_size}

try:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
    manifest=json.loads((OUT/'media/manifest.json').read_text())
    created=False
    for take in manifest:
        path='/Game/Audition/Reactions/LS_Neck_'+take['name']
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            seq=unreal.EditorAssetLibrary.duplicate_asset('/Game/Audition/Sequences/LS_Closeup_'+take['name'],path)
            unreal.EditorAssetLibrary.save_loaded_asset(seq)
            created=True
    if created:
        report['status']='copies_saved_restart_required'
        sys.exit(0)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    meshes={part:unreal.load_asset('/Game/MetaHumans/AuditionMale/'+part+'/SKM_AuditionMale_'+part+'Mesh') for part in ['Face','Body']}
    for part,mesh in meshes.items():
        if not mesh:raise RuntimeError('Missing mesh: '+part)
        file=part.lower()+'_model.fbx'
        if not (FILES/file).exists():fbx(mesh,file)
        report['model_files'].append({'file':file,'bytes':(FILES/file).stat().st_size})
    for take in json.loads((OUT/'media/manifest.json').read_text()):
        name=take['name'];count=take['frames']
        report['status']='baking_'+name;save()
        path='/Game/Audition/Reactions/LS_Neck_'+name
        seq=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/Game/Audition/Sequences/LS_Closeup_'+name,path)
        motion=unreal.load_asset('/Game/Audition/Baked/AS_RawMotion_'+name)
        if not motion:raise RuntimeError('Export the captured head curves first')
        # Gentle offline smoothing, with no extrapolation or body translation.
        values={axis:[unreal.AnimationLibrary.get_float_value_at_time(motion,curve,i/30) for i in range(count)]
                for axis,curve in [('X','HeadRoll'),('Y','HeadPitch'),('Z','HeadYaw')]}
        smooth={axis:[sum(v[max(0,min(count-1,i+d))]*w for d,w in [(-2,1),(-1,2),(0,3),(1,2),(2,1)])/9 for i in range(count)] for axis,v in values.items()}
        # Drive the active head IK target. The rig distributes its orientation
        # through the neck; FK offsets alone leave the skull locked in place.
        shares={'neck_01_ctrl':0.0,'neck_02_ctrl':0.0,'head_ctrl':0.0,'head_ik_ctrl':1.0}
        channels_written=0
        report['binding_diagnostic']=[{'binding':str(b.get_display_name()),'channels':[str(c.get_name()) for t in b.get_tracks() for s in t.get_sections() for c in s.get_all_channels() if 'neck' in str(c.get_name()).lower() or 'head_ctrl' in str(c.get_name()).lower()]} for b in seq.get_bindings()]
        save()
        for binding in seq.get_bindings():
            if str(binding.get_display_name())!='Body':continue
            for track in binding.get_tracks():
                for section in track.get_sections():
                    if isinstance(section,unreal.MovieSceneControlRigParameterSection):
                        enabled=list(shares)+['head_local','neck_fk_ik_switch']
                        report['control_mask_before']={c:unreal.ControlRigSequencerLibrary.get_controls_mask(section,c) for c in enabled}
                        unreal.ControlRigSequencerLibrary.set_controls_mask(section,enabled,True)
                        save()
                    for channel in section.get_all_channels():
                        label=str(channel.get_editor_property('channel_name'))
                        if label=='head_local':channel.set_default(False)
                        if label=='neck_fk_ik_switch':channel.set_default(True)
                        for control,share in shares.items():
                            for axis in ['X','Y','Z']:
                                if label!=control+'.Rotation.'+axis:continue
                                for key in channel.get_keys():channel.remove_key(key)
                                for i,value in enumerate(smooth[axis]):
                                    channel.add_key(unreal.FrameNumber(i),value*share,interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
                                channels_written+=1
        if channels_written!=len(shares)*3:raise RuntimeError(f'{name}: only wrote {channels_written} neck/head channels')
        unreal.EditorAssetLibrary.save_loaded_asset(seq)
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
        row={'name':name,'sequence':seq.get_path_name(),'source_frames':count,'fps':30,
             'rotation_distribution':shares,'rotation_ranges':{k:[min(v),max(v)] for k,v in smooth.items()},
             'translation_enabled':False,'clips':[]}
        report['reactions'].append(row);save()
        for part,mesh in meshes.items():
            binding=next(b for b in seq.get_bindings() if str(b.get_display_name())==part)
            anim_name='AS_'+name+'_'+part
            anim_path='/Game/Audition/Reactions/'+anim_name
            if unreal.EditorAssetLibrary.does_asset_exist(anim_path):
                anim=unreal.load_asset(anim_path)
            else:
                factory=unreal.AnimSequenceFactory()
                factory.target_skeleton=mesh.get_editor_property('skeleton')
                anim=tools.create_asset(anim_name,'/Game/Audition/Reactions',unreal.AnimSequence,factory)
            options=unreal.AnimSeqExportOption()
            options.export_transforms=True
            options.export_morph_targets=True
            options.export_attribute_curves=True
            options.export_material_curves=True
            options.evaluate_all_skeletal_mesh_components=True
            options.record_in_world_space=False
            options.delay_before_start=unreal.FrameNumber(8)
            options.warm_up_frames=unreal.FrameNumber(0)
            options.use_custom_frame_rate=True
            options.custom_frame_rate=unreal.FrameRate(30,1)
            options.use_custom_time_range=True
            options.custom_start_frame=unreal.FrameNumber(0)
            options.custom_end_frame=unreal.FrameNumber(count-1)
            options.custom_display_rate=unreal.FrameRate(30,1)
            if not unreal.ControlRigSequencerLibrary.export_anim_sequence_from_sequencer(anim,options,binding,False):
                raise RuntimeError('Evaluated animation bake failed: '+anim_name)
            unreal.EditorAssetLibrary.save_loaded_asset(anim)
            names=list(unreal.AnimationLibrary.get_animation_track_names(anim))
            varying=[]
            for bone in names:
                poses=[unreal.AnimationLibrary.get_bone_pose_for_frame(anim,bone,f,False) for f in [0,count//4,count//2,3*count//4,count-1]]
                if len({tuple(round(float(getattr(p.rotation,a)),5) for a in ['x','y','z','w'])+tuple(round(float(getattr(p.translation,a)),5) for a in ['x','y','z']) for p in poses})>1:
                    varying.append(str(bone))
            report['last_bake_diagnostic']={'part':part,'tracks':len(names),'first_names':[str(n) for n in names[:8]],'varying':varying[:12]}
            save()
            if not varying:raise RuntimeError('No evaluated bone motion found: '+anim_name)
            if 'head' not in varying:raise RuntimeError('Head orientation did not bake: '+anim_name)
            exported=fbx(anim,name+'_'+part.lower()+'.fbx')
            row['clips'].append({'part':part,'asset':anim.get_path_name(),'bone_tracks':len(names),
                                 'animated_bones':len(varying),'animated_neck_bones':[n for n in varying if n in ['head','neck_01','neck_02']],**exported})
            save()
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    report['status']='baked_and_exported'
except Exception:
    report['status']='error';report['error']=traceback.format_exc();unreal.log_error(report['error'])
finally:
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    save()
