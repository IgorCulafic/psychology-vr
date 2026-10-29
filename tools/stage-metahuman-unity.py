"""Convert exported material inputs to portable URP textures; keep source exports intact."""
import json,hashlib,shutil
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'experiments/metahuman/exports/unity'
DST=ROOT/'unity/Assets/PsychologyVR/Art/MetaHumans'
DST.mkdir(parents=True,exist_ok=True)
m=json.loads((SRC/'manifest.json').read_text())
uv_channels=json.loads((SRC/'hair-uv-channels.json').read_text())
assert m['status']=='exported'
def copy(file):
    target=DST/file;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or target.stat().st_mtime<(SRC/file).stat().st_mtime:shutil.copy2(SRC/file,target)
    return file
def tx(path):return copy(m['textures'][path]['file']) if path else ''
def image(path):return Image.open(SRC/m['textures'][path]['file']).convert('RGBA')
out={'characters':[],'materials':[]}
for path,r in m['materials'].items():
    name=r['name'];t=r['textures'];key=hashlib.sha256(path.encode()).hexdigest()[:12]
    color=t.get('Basecolor Baked',t.get('BaseColor',t.get('Basecolor Original')))
    normal=t.get('Normal Baked',t.get('Normal',t.get('normalmap')))
    tint=[1,1,1,1];alpha='';smooth=.3
    if 'DefaultGarment' in name:
        color=None;tint=r['vectors'].get('diffuse_color_1',tint);smooth=.18
    if 'EyeL_' in name or 'EyeR_' in name:
        # MetaHuman eye UVs use a central iris disk. Bake it into a conventional eye map.
        sclera=image(t['Sclera Basecolor Baked']).resize((1024,1024))
        iris=Image.new('RGBA',(1024,1024));iris.paste(image(t['Iris Basecolor Baked']).resize((298,298)),(363,363))
        yy,xx=np.mgrid[0:1024,0:1024];rad=np.sqrt((xx-511.5)**2+(yy-511.5)**2)/1024
        a=np.clip((.145-rad)/.005,0,1)[...,None]
        pixels=np.asarray(sclera)*(1-a)+np.asarray(iris)*a
        file=f'textures/eye_{key}.png';(DST/'textures').mkdir(exist_ok=True)
        Image.fromarray(pixels.astype('uint8')).save(DST/file);color=None;normal=None;smooth=.85
    else:file=tx(color)
    if name=='M_Hide' or 'EyeShell' in name or 'LacrimalFluid' in name:alpha='hidden'
    if 'Eyelashes' in name:alpha='hidden' # Export has placeholder black map, not strand lashes.
    out['materials'].append({'key':path,'id':key,'name':name,'colorMap':file,'normalMap':tx(normal),'color':tint,'mode':alpha,'smoothness':smooth})
for c in m['characters']:
    row={k:c[k] for k in ['id','label','scenario','voice']};row['meshes']=[]
    for mesh in c['meshes']:
        item=dict(mesh);item['file']=copy(mesh['file'])
        if mesh['type']=='hair_cards':
            item['uvChannel']=uv_channels[mesh['file']]['channel']
            atlas=mesh['atlas'];layout=int(mesh['texture_layout'].split(': ')[1].rstrip('>'))
            cov=image(atlas[2] if layout==3 else atlas[1])
            rgba=np.zeros((cov.height,cov.width,4),dtype=np.uint8);rgba[:,:,:3]=[38,27,20]
            if layout==2 and len(atlas)>2 and atlas[2]:rgba[:,:,:3]=np.asarray(image(atlas[2]).resize(cov.size))[:,:,:3]
            rgba[:,:,3]=np.asarray(cov)[:,:,3 if layout==3 else 0]
            file=f"{c['id']}/{mesh['name']}_RGBA.png";Image.fromarray(rgba).save(DST/file)
            item['hairMap']=file
        row['meshes'].append(item)
    row['clips']=[]
    perf=SRC/'performance.json'
    if perf.exists():
        p=json.loads(perf.read_text());pc=next((x for x in p['characters'] if x['id']==c['id']),None)
        if pc:
            row['poses']=pc['poses']
            for clip in pc['clips']:row['clips'].append(dict(clip,file=copy(clip['file'])))
    out['characters'].append(row)
(DST/'manifest.json').write_text(json.dumps(out,indent=2))
print('Staged',len(out['characters']),'characters,',len(out['materials']),'materials')
