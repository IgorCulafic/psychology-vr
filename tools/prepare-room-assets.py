"""Blender: convert the selected glTFs to FBX and retain explicit URP maps."""
import bpy, json, shutil, math
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.cache/assets/polyhaven'
OUT=ROOT/'unity/Assets/PsychologyVR/Art/Environment'
OUT.mkdir(parents=True,exist_ok=True)
materials=[]
audit=[]
bindings=[]

def copy_texture(path):
    if not path: return ''
    target=OUT/'Textures'/path.name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,target)
    return 'Assets/PsychologyVR/Art/Environment/Textures/'+target.name

def packed_map(path,name,roughness=1,metallic=1):
    img=bpy.data.images.load(str(path),check_existing=False)
    img.colorspace_settings.name='Non-Color'
    pixels=np.empty(len(img.pixels),dtype=np.float32); img.pixels.foreach_get(pixels)
    rgba=pixels.reshape(-1,4).copy()
    rgba[:,0]=rgba[:,2]*metallic; rgba[:,1:3]=0; rgba[:,3]=1-pixels.reshape(-1,4)[:,1]*roughness
    result=bpy.data.images.new(name,img.size[0],img.size[1],alpha=True)
    result.colorspace_settings.name='Non-Color'; result.pixels.foreach_set(rgba.ravel())
    target=OUT/'Textures'/(name+'_metal_smooth.png'); target.parent.mkdir(parents=True,exist_ok=True)
    result.filepath_raw=str(target); result.file_format='PNG'; result.save()
    bpy.data.images.remove(img); bpy.data.images.remove(result)
    return 'Assets/PsychologyVR/Art/Environment/Textures/'+target.name

for source in sorted(SOURCE.glob('*/*.gltf')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data=json.loads(source.read_text()); asset=source.parent.name
    # Unique material names make Unity remapping deterministic.
    for i,mat in enumerate(data.get('materials',[])): mat['name']=asset+'_mat_'+str(i)
    temp=source.with_name('unity-conversion.gltf'); temp.write_text(json.dumps(data))
    bpy.ops.import_scene.gltf(filepath=str(temp)); temp.unlink()
    for mat in data.get('materials',[]):
        pbr=mat.get('pbrMetallicRoughness',{})
        def texture(ref):
            if not ref: return None
            return source.parent/data['images'][data['textures'][ref['index']]['source']]['uri']
        base=texture(pbr.get('baseColorTexture')); normal=texture(mat.get('normalTexture')); orm=texture(pbr.get('metallicRoughnessTexture'))
        materials.append({'name':mat['name'],'baseMap':copy_texture(base),'normalMap':copy_texture(normal),
            'metalMap':packed_map(orm,mat['name'],pbr.get('roughnessFactor',1),pbr.get('metallicFactor',1)) if orm else '',
            'color':pbr.get('baseColorFactor',[1,1,1,1]),'metallic':pbr.get('metallicFactor',1),
            'smoothness':1-pbr.get('roughnessFactor',1),'cutout':mat.get('alphaMode')=='MASK','doubleSided':mat.get('doubleSided',False)})
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    budget=18000 if asset.startswith('potted_plant') else (6000 if asset=='binder_notebook' else 100000)
    original_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
    if original_triangles>budget:
        for o in meshes:
            bpy.context.view_layer.objects.active=o
            modifier=o.modifiers.new('VR polygon budget','DECIMATE'); modifier.ratio=budget/original_triangles
            bpy.ops.object.modifier_apply(modifier=modifier.name)
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    low=Vector(tuple(min(p[i] for p in points) for i in range(3))); high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    shift=Vector((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z))
    for o in meshes:
        # Bake parent transforms so exported pivots share a floor-centered origin.
        matrix=o.matrix_world.copy(); o.parent=None; o.matrix_world=matrix; o.location+=shift
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes: o.select_set(True)
    for o in meshes:
        indices=[p.material_index for p in o.data.polygons]; used=sorted(set(indices))
        selected=[o.data.materials[i] for i in used]; o.data.materials.clear()
        for m in selected:o.data.materials.append(m)
        for poly,i in zip(o.data.polygons,indices):poly.material_index=used.index(i)
        bindings.append({'asset':asset,'renderer':o.name,'materials':[m.name for m in o.data.materials]})
    target=OUT/'Models'/(asset+'.fbx'); target.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(target),use_selection=True,object_types={'MESH'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='STRIP')
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
    audit.append({'id':asset,'dimensions_xyz_blender':list(high-low),'triangles':triangles})
    print('ROOM_ASSET '+asset+' '+str(audit[-1]),flush=True)

for asset in ['wood_floor','white_plaster_02']:
    for image in (SOURCE/asset).glob('*.jpg'): copy_texture(image)
(OUT/'materials.json').write_text(json.dumps({'materials':materials},indent=2))
(OUT/'bindings.json').write_text(json.dumps({'bindings':bindings},indent=2))
(ROOT/'docs/generated/room-asset-audit.json').write_text(json.dumps(audit,indent=2))
