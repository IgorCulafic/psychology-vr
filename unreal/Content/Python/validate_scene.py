"""Audit generated scene transforms and tune the port's physical light units."""
import json
from pathlib import Path
import unreal as u

root = Path(u.Paths.project_dir()).resolve().parent
level = u.get_editor_subsystem(u.LevelEditorSubsystem)
level.load_level('/Game/Psychology/Consultation')
actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
report = []
for actor in actors:
    name = actor.get_actor_label()
    yaw = {'side_table_01': -12, 'tissue_box': -12, 'binder_notebook': -9,
           'pencil': -10, 'modern_coffee_table_01': 90,
           'Patient - animation tool integration point': 180}.get(name)
    if name == 'modern_arm_chair_01': yaw = 180 if actor.get_actor_location().x > 0 else 0
    if name == 'potted_plant_02': yaw = -30 if actor.get_actor_location().x > 200 else 0
    if isinstance(actor,u.StaticMeshActor) and yaw is None: yaw=0
    if yaw is not None: actor.set_actor_rotation(u.Rotator(pitch=0,yaw=yaw-90,roll=0),False)
    if name=='modern_ceiling_lamp_01': actor.static_mesh_component.set_cast_shadow(False)
    origin, extent = actor.get_actor_bounds(False)
    row = {'name': actor.get_actor_label(), 'location': str(actor.get_actor_location()),
           'rotation': str(actor.get_actor_rotation()), 'bounds_origin': str(origin), 'bounds_extent': str(extent)}
    if isinstance(actor, u.PointLight):
        actor.point_light_component.set_editor_property('intensity_units', u.LightUnits.LUMENS)
    if actor.get_class().get_name() == 'PsychologyPatient':
        body = actor.get_editor_property('body')
        idle=u.EditorAssetLibrary.load_asset('/Game/Psychology/Generated/Character/SeatedIdle')
        if idle:
            data=body.get_editor_property('animation_data')
            data.set_editor_property('anim_to_play',idle)
            body.set_editor_property('animation_data',data)
        for i,slot in enumerate(body.get_skeletal_mesh_asset().materials):
            material_name=str(slot.get_editor_property('material_slot_name')).replace('.','_')
            mat=u.EditorAssetLibrary.load_asset('/Game/Psychology/Generated/Character/Materials/'+material_name)
            if mat: body.set_material(i,mat)
        row['animation'] = str(body.get_editor_property('animation_data'))
        row['materials'] = [str(body.get_material(i)) for i in range(body.get_num_materials())]
    report.append(row)
existing = next((a for a in actors if a.get_actor_label() == 'Consultation exposure'), None)
volume = existing or u.get_editor_subsystem(u.EditorActorSubsystem).spawn_actor_from_class(u.PostProcessVolume, u.Vector())
volume.set_actor_label('Consultation exposure')
volume.set_editor_property('unbound', True)
settings = volume.get_editor_property('settings')
settings.set_editor_property('override_auto_exposure_method', True)
settings.set_editor_property('auto_exposure_method', u.AutoExposureMethod.AEM_MANUAL)
settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure', True)
settings.set_editor_property('auto_exposure_apply_physical_camera_exposure', False)
settings.set_editor_property('override_auto_exposure_bias', True)
settings.set_editor_property('auto_exposure_bias', -3.0)
volume.set_editor_property('settings', settings)
level.save_current_level()
(root / 'docs/generated/unreal-scene-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
u.log('PSYCHOLOGY_SCENE_AUDITED')
