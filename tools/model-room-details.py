"""Create original room architecture, tissue box and desk props in Blender.
Unity coordinates are converted to Blender before export; dimensions are metres.
"""
import bpy, math, json
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'unity/Assets/PsychologyVR/Art/Environment'
bpy.ops.wm.read_factory_settings(use_empty=True)
specs=[]
bindings=[]
def mat(name,color,rough=.7,base='',normal=''):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1)
    specs.append({'name':name,'color':[*color,1],'smoothness':1-rough,'metallic':0,'baseMap':base,'normalMap':normal,'doubleSided':False})
    return m
tex='Assets/PsychologyVR/Art/Environment/Textures/'
plaster=mat('Room_Plaster',(.87,.83,.75),.9,tex+'white_plaster_02_diff.jpg',tex+'white_plaster_02_nor_gl.jpg')
sage=mat('Room_Sage',(.45,.55,.49),.9,tex+'white_plaster_02_diff.jpg',tex+'white_plaster_02_nor_gl.jpg')
oak=mat('Room_Oak',(.8,.69,.52),.55,tex+'wood_floor_diff.jpg',tex+'wood_floor_nor_gl.jpg')
trim=mat('Room_Trim',(.86,.82,.73))
linen=mat('Room_Linen',(.77,.72,.61),.96)
dark=mat('Room_DarkBronze',(.07,.075,.07),.3)
paper=mat('Room_Paper',(.94,.92,.87),.96)
ceramic=mat('Room_Ceramic',(.38,.47,.43),.27)
taupe=mat('Room_Rug',(.40,.38,.32),1)
sky=mat('Room_WindowLight',(.76,.86,.89),.8)
ink=mat('Room_Ink',(.16,.24,.20))

def pos(p):return (p[0],-p[2],p[1])
def box(name,p,size,m,bevel=.012):
    bpy.ops.mesh.primitive_cube_add(size=1,location=pos(p)); o=bpy.context.object; o.name=name
    o.dimensions=(size[0],size[2],size[1]); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL'); bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.materials.append(m)
    # Physical UV scale keeps plaster fine and floorboards believable.
    for poly in o.data.polygons:
        normal=poly.normal; axis=max(range(3),key=lambda i:abs(normal[i])); axes=[i for i in range(3) if i!=axis]
        for li in poly.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co
            o.data.uv_layers.active.data[li].uv=(v[axes[0]]*.5,v[axes[1]]*.5)
    return o
def rod(name,a,b,r,m,vertices=20):
    start,end=Vector(pos(a)),Vector(pos(b)); delta=end-start
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=delta.length,location=(start+end)/2)
    o=bpy.context.object;o.name=name;o.rotation_euler=delta.to_track_quat('Z','Y').to_euler();o.data.materials.append(m)
    for p in o.data.polygons:p.use_smooth=True
    return o
def export(name):
    bpy.ops.object.select_all(action='SELECT')
    for o in bpy.context.selected_objects:
        if o.type=='MESH':
            indices=[p.material_index for p in o.data.polygons]; used=sorted(set(indices))
            fallback=next((m for m in o.data.materials if m),paper)
            selected=[o.data.materials[i] if i<len(o.data.materials) and o.data.materials[i] else fallback for i in used]
            o.data.materials.clear()
            for m in selected:o.data.materials.append(m)
            for p,i in zip(o.data.polygons,indices):p.material_index=used.index(i)
            bindings.append({'asset':name,'renderer':o.name,'materials':[m.name for m in o.data.materials]})
    bpy.ops.export_scene.fbx(filepath=str(OUT/'Models'/(name+'.fbx')),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='STRIP')
    bpy.ops.object.delete(use_global=False)

# Six-sided room, real window opening, baseboards, panel details and doorway.
box('Oak floor',(0,-.065,0),(6.16,.13,6.16),oak)
box('Sage back wall',(0,1.45,3),(6.1,2.9,.14),sage)
box('Right plaster',(3,1.45,0),(.14,2.9,6),plaster)
box('Front plaster',(0,1.45,-3),(6.1,2.9,.14),plaster)
box('Ceiling',(0,2.96,0),(6.16,.12,6.16),plaster)
for z,depth in [(-1.7,2.6),(2.55,.9)]:box('Window wall pier',(-3,1.45,z),(.14,2.9,depth),plaster)
box('Window lower wall',(-3,.46,.85),(.14,.92,2.5),plaster)
box('Window upper wall',(-3,2.71,.85),(.14,.38,2.5),plaster)
box('Window exterior',(-3.085,1.72,.85),(.02,1.55,2.5),sky)
for z in [-.4,.85,2.1]:box('Window vertical frame',(-2.97,1.72,z),(.12,1.62,.045),trim,.003)
for y in [.94,2.5]:box('Window horizontal frame',(-2.96,y,.85),(.14,.065,2.55),trim,.004)
box('Window sill',(-2.88,.94,.85),(.36,.075,2.72),oak)
for x in [-2.92,2.92]:box('Skirting',(x,.075,0),(.035,.15,6),trim,.003)
for z in [-2.92,2.92]:box('Skirting',(0,.075,z),(6,.15,.035),trim,.003)
# Door on right wall; visible from the seated player's peripheral view.
box('Door frame',(2.9,1.1,-1.7),(.08,2.2,1),trim)
box('Oak door',(2.84,1.055,-1.7),(.045,2.1,.88),oak)
rod('Door handle',(2.77,1,-1.42),(2.77,1,-1.62),.016,dark)
# Pleated curtains, modeled cloth strips around the window.
for center in [-.39,2.1]:
    verts=[];faces=[]; nx=28;ny=8
    for j in range(ny+1):
        for i in range(nx+1):
            u=i/nx;v=j/ny
            verts.append(pos((-2.76+.045*math.cos(u*math.pi*10),.24+v*2.37,center+(u-.5)*.57)))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
    mesh=bpy.data.meshes.new('Linen folds');mesh.from_pydata(verts,[],faces);o=bpy.data.objects.new('Curtain',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(linen)
    solid=o.modifiers.new('Cloth thickness','SOLIDIFY');solid.thickness=.003
    for p in mesh.polygons:p.use_smooth=True
rod('Curtain rail',(-2.74,2.65,-.76),(-2.74,2.65,2.48),.015,dark)
box('Woven rug',(0,.012,.22),(3.1,.024,3.1),taupe,.018)
for x in [-1.48,1.48]:box('Rug border',(x,.026,.22),(.022,.002,2.95),linen,.001)
for z in [-1.25,1.69]:box('Rug border',(0,.026,z),(2.98,.002,.022),linen,.001)
# Three framed botanical reliefs; original geometry rather than borrowed art.
for idx,x in enumerate([-.86,0,.86]):
    box('Oak picture frame',(x,1.94,2.885),(.66,.84,.055),oak,.008)
    box('Picture mount',(x,1.94,2.849),(.59,.77,.016),paper,.002)
    rod('Botanical stem',(x,1.63,2.834),(x+.05,2.18,2.834),.004,ink,8)
    for k in range(5):
        s=-1 if k%2 else 1;y=1.7+k*.09
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,location=pos((x+s*.075,y,2.825)))
        o=bpy.context.object;o.name='Botanical leaf';o.scale=(.09,.004,.035);o.rotation_euler[1]=s*.45;o.data.materials.append(ink)
# Shelf and small books in a quiet corner.
box('Floating shelf',(-1.94,1.32,2.77),(1.22,.055,.31),oak)
for i in range(8):
    color=mat('Book_'+str(i),[(.32,.39,.34),(.55,.38,.25),(.73,.67,.53)][i%3])
    box('Book binding',(-2.36+i*.065,1.5+(i%3)*.014,2.76),(.047,.29+(i%3)*.028,.20),color,.004)
export('consultation_architecture')

# Custom tissue box: rounded casing, recessed oval slot, seams and folded paper.
case=box('Tissue box casing',(0,.056,0),(.245,.112,.135),linen,.009)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=12,location=pos((0,.114,0)))
cutter=bpy.context.object;cutter.scale=(.084,.022,.019);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bpy.context.view_layer.objects.active=case;boolean=case.modifiers.new('Recessed dispenser slot','BOOLEAN');boolean.object=cutter;boolean.operation='DIFFERENCE';bpy.ops.object.modifier_apply(modifier=boolean.name);bpy.data.objects.remove(cutter,do_unlink=True)
box('Bottom seam',(0,.008,0),(.247,.004,.137),trim,.001)
verts=[];faces=[];nx=22;ny=20
for j in range(ny+1):
    v=j/ny
    for i in range(nx+1):
        u=i/nx;verts.append(pos(((u-.5)*(.10+.06*v),.108+.14*v+.013*math.sin(u*math.pi*3)*v,.004+math.sin(u*math.pi*4)*.009*v+.035*v*v)))
for j in range(ny):
    for i in range(nx):
        a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
mesh=bpy.data.meshes.new('Folded tissue');mesh.from_pydata(verts,[],faces);o=bpy.data.objects.new('Soft paper tissue',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(paper)
solid=o.modifiers.new('Paper thickness','SOLIDIFY');solid.thickness=.0007
for p in mesh.polygons:p.use_smooth=True
export('tissue_box')

# A ceramic water cup and pencil for the player's desk.
rod('Cup body',(0,.008,0),(0,.098,0),.037,ceramic,48)
rod('Water surface',(0,.100,0),(0,.101,0),.031,dark,48)
bpy.ops.mesh.primitive_torus_add(major_radius=.034,minor_radius=.003,major_segments=48,minor_segments=8,location=pos((0,.101,0)))
bpy.context.object.data.materials.append(ceramic)
export('water_cup')
rod('Pencil',(0,.006,-.085),(0,.006,.085),.004,oak,6)
export('pencil')
(OUT/'custom-materials.json').write_text(json.dumps({'materials':specs},indent=2))
(OUT/'custom-bindings.json').write_text(json.dumps({'bindings':bindings},indent=2))
print('ROOM_DETAILS_OK')
