"""Extend the supplied MetaHuman garments into trousers and add lightweight shoes.

Run with Blender. Source FBXs remain untouched; no new external assets are needed.
"""
import bpy,bmesh,math,json
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'experiments/metahuman/exports/unity'
DST=ROOT/'unity/Assets/PsychologyVR/Art/MetaHumans'
report=[]
for cid in ['ivan','stefan','nikola','alex']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.fbx(filepath=str(SRC/cid/'models/SkeletalMesh.fbx'))
 garment=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
 # Transform positions in world metres, independently of FBX's centimetre armature.
 shorts=set(v for p in garment.data.polygons if 'Short' in garment.data.materials[p.material_index].name for v in p.vertices)
 points={i:garment.matrix_world@garment.data.vertices[i].co for i in shorts}
 bottom=min(v.z for v in points.values());top=max(v.z for v in points.values())
 cut=bottom+(top-bottom)*.48
 ankle=(arm.matrix_world@arm.data.bones['foot_l'].head_local).z
 target=ankle-.025
 inv=garment.matrix_world.inverted()
 for i,p in points.items():
  if p.z>=cut:continue
  t=(cut-p.z)/(cut-bottom);p.z=cut-t*(cut-target)
  # A slight taper gives the existing folded hem a normal trouser cuff.
  side='l' if p.x>0 else 'r'
  knee=arm.matrix_world@arm.data.bones['calf_'+side].head_local
  foot=arm.matrix_world@arm.data.bones['foot_'+side].head_local
  center=knee.lerp(foot,max(0,min(1,(knee.z-p.z)/(knee.z-foot.z))))
  old_center=Vector((math.copysign(.09,p.x),-.027,p.z))
  taper=1-.45*t
  center=old_center.lerp(center,t)
  p.x=center.x+(p.x-old_center.x)*taper
  p.y=center.y+(p.y-old_center.y)*taper
  # Restrained folds; the original upper garment and seams remain intact.
  fold=.0025*math.sin(t*math.pi*9)*math.sin(t*math.pi)
  p.y+=fold;p.x+=math.copysign(fold*.35,p.x)
  garment.data.vertices[i].co=inv@p
  for g in garment.vertex_groups:g.remove([i])
  blend=max(0,min(1,(knee.z+.085-p.z)/.17));blend=blend*blend*(3-2*blend)
  # Continuous thigh/knee weights avoid nearest-vertex switches and prevent the
  # trouser cuff from following the foot's independent rotation.
  for name,weight in [('thigh_'+side,1-blend),('calf_'+side,blend)]:
   group=garment.vertex_groups.get(name) or garment.vertex_groups.new(name=name)
   group.add([i],weight,'REPLACE')
 # Recalculate normals after extending the cuffs.
 bm=bmesh.new();bm.from_mesh(garment.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(garment.data);bm.free()
 shoes=[]
 for side in ['l','r']:
  foot=arm.matrix_world@arm.data.bones['foot_'+side].head_local
  ball=arm.matrix_world@arm.data.bones['ball_'+side].head_local
  forward=Vector((ball.x-foot.x,ball.y-foot.y,0)).normalized();right=Vector((-forward.y,forward.x,0))
  length=(ball-foot).xy.length+.075
  # Rounded trainer profile from heel to toe; sole and upper are separate materials.
  profiles=[(-.060,.025,.040),(-.048,.052,.082),(-.018,.058,.105),(.025,.062,.105),(.080,.061,.085),(length-.035,.055,.063),(length-.010,.033,.047),(length,.005,.029)]
  verts=[];faces=[];mats=[];n=24
  for d,w,h in profiles:
   for j in range(n):
    a=2*math.pi*j/n;z=.012+(h-.012)*(math.sin(a)+1)/2
    verts.append(tuple(foot+forward*d+right*(w*math.cos(a))+Vector((0,0,z-foot.z))))
  for k in range(len(profiles)-1):
   for j in range(n):
    faces.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j));mats.append(1 if math.sin(2*math.pi*(j+.5)/n)<-.72 else 0)
  faces.extend([tuple(reversed(range(n))),tuple((len(profiles)-1)*n+j for j in range(n))]);mats.extend([0,0])
  mesh=bpy.data.meshes.new('Trainer_'+side);mesh.from_pydata(verts,[],faces);mesh.update()
  shoe=bpy.data.objects.new('Trainer_'+side,mesh);bpy.context.collection.objects.link(shoe)
  for name in ['Casual_Shoe','Rubber_Sole']:
   mat=bpy.data.materials.get(name) or bpy.data.materials.new(name);mesh.materials.append(mat)
  for p,mat in zip(mesh.polygons,mats):p.material_index=mat;p.use_smooth=True
  vg=shoe.vertex_groups.new(name='foot_'+side);vg.add(list(range(len(verts))),1,'REPLACE')
  modifier=shoe.modifiers.new('Body rig','ARMATURE');modifier.object=arm
  # Small flat lace strips read clearly without extra textures or simulation.
  for k in range(4):
   d=.025+k*.019;z=.105-k*.005
   bpy.ops.mesh.primitive_cube_add(size=1,location=foot+forward*d+Vector((0,0,z-foot.z+.002)))
   lace=bpy.context.object;lace.name='Lace';lace.rotation_euler.z=math.atan2(right.y,right.x);lace.scale=(.079,.0035,.002)
   bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
   lace.data.materials.append(bpy.data.materials.get('Rubber_Sole'))
   vg=lace.vertex_groups.new(name='foot_'+side);vg.add(list(range(len(lace.data.vertices))),1,'REPLACE')
   mod=lace.modifiers.new('Body rig','ARMATURE');mod.object=arm;shoes.append(lace)
  shoes.append(shoe)
 bpy.ops.object.select_all(action='DESELECT')
 for o in [garment,arm]+shoes:o.select_set(True)
 bpy.context.view_layer.objects.active=arm
 out=DST/cid/'models/Outfit.fbx'
 bpy.ops.export_scene.fbx(filepath=str(out),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=True)
 report.append({'id':cid,'file':str(out),'shorts_vertices_extended':sum(p.z<cut for p in points.values()),'ankle_m':ankle,'source_preserved':True})
(SRC/'clothing-build.json').write_text(json.dumps(report,indent=2))
print('CLOTHES_BUILT',len(report))
