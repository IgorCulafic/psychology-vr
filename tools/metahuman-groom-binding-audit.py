import unreal,json
from pathlib import Path
root=Path('D:/AI/Psychology_VR');out=[]
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/Audition/Studio')
a=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for name in ['Ivan','Stefan','Nikola','AuditionMale']:
 actor=a.spawn_actor_from_class(unreal.load_asset('/Game/MetaHumans/'+name+'/BP_'+name).generated_class(),unreal.Vector())
 for c in actor.get_components_by_class(unreal.GroomComponent):
  b=c.get_editor_property('binding_asset')
  if b:
   source=b.get_editor_property('source_skeletal_mesh');target=b.get_editor_property('target_skeletal_mesh')
   out.append(dict(character=name,part=c.get_name(),binding=b.get_path_name(),source=source.get_path_name() if source else None,target=target.get_path_name() if target else None))
 a.destroy_actor(actor)
(root/'experiments/metahuman/exports/unity/groom-bindings.json').write_text(json.dumps(out,indent=2))
unreal.SystemLibrary.quit_editor()

