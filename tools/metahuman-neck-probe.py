import json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[1]
report={}
for name in ['afraid','crying','angry']:
    perf=unreal.load_asset('/Game/Audition/'+name+'/Performance')
    path='/Game/Audition/Baked/AS_RawMotion_'+name
    anim=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if not anim:
        settings=unreal.MetaHumanPerformanceExportAnimationSettings()
        settings.show_export_dialog=False
        settings.package_path='/Game/Audition/Baked'
        settings.asset_name='AS_RawMotion_'+name
        settings.target_skeleton_or_skeletal_mesh=unreal.load_asset('/Game/MetaHumans/AuditionMale/Face/SKM_AuditionMale_FaceMesh')
        settings.enable_head_movement=True
        anim=unreal.MetaHumanPerformanceExportUtils.export_animation_sequence(perf,settings)
    if not anim: raise RuntimeError('No motion animation: '+name)
    report[name]={}
    for curve in ['HeadRoll','HeadPitch','HeadYaw']:
        times,values=unreal.AnimationLibrary.get_float_keys(anim,curve)
        report[name][curve]={'times':list(times),'values':list(values)}
(ROOT/'experiments/metahuman/neck-probe.json').write_text(json.dumps(report,indent=2))
seq=unreal.load_asset('/Game/Audition/Sequences/LS_Closeup_afraid')
rigs=unreal.ControlRigSequencerLibrary.get_control_rigs(seq)
report['rigs']=[]
for proxy in rigs:
    rig=proxy.control_rig
    hierarchy=rig.get_hierarchy()
    row={'name':rig.get_name(),'controls':{}}
    for key in hierarchy.get_controls():
        if str(key.name) in ['neck_01_ctrl','neck_02_ctrl','head_ctrl']:
            tr=hierarchy.get_global_transform(key,True)
            q=tr.rotation
            row['controls'][str(key.name)]={'q':[q.x,q.y,q.z,q.w],'transform':str(tr)}
    report['rigs'].append(row)
report['bone_pose_doc']=unreal.AnimationLibrary.get_bone_pose_for_frame.__doc__
report['raw_rotation_doc']=unreal.AnimationLibrary.get_raw_track_rotation_data.__doc__
report['track_names_doc']=unreal.AnimationLibrary.get_animation_track_names.__doc__
(ROOT/'experiments/metahuman/neck-probe.json').write_text(json.dumps(report,indent=2))
