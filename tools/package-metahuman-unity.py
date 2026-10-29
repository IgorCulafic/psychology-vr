"""Publish the desktop validation captures to the existing local review server."""
from pathlib import Path
import html,json,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/generated/face-library-review/metahuman-unity';OUT.mkdir(parents=True,exist_ok=True)
cast=json.loads((ROOT/'experiments/metahuman/cast.json').read_text())['characters']
cards=[]
for i,c in enumerate(cast):
    target=OUT/c['id'];target.mkdir(exist_ok=True)
    for mood in ['neutral','angry','crying','afraid','happy','sad','disgusted','speaking','body']:
        shutil.copy2(ROOT/f'experiments/metahuman/unity-review/{i}-{mood}.png',target/f'{mood}.png')
    for mood in ['room','crying']:
        shutil.copy2(ROOT/f'experiments/metahuman/unity-room-review/{c["id"]}-{mood}.png',target/f'room-{mood}.png')
    cards.append(f'''<article><h2>{html.escape(c['label'])}</h2><p>{html.escape(c['scenario'])} · {html.escape(c['voice'].replace('igor_2026-10-03','Igor').replace('person_','Person '))}</p><img src="{c['id']}/neutral.png" data-person="{c['id']}" alt="Unity capture of {c['label']}"></article>''')
(OUT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>MetaHuman · Unity integration</title>
<style>body{font:17px system-ui;background:#131b1d;color:#edf0ea;max-width:1500px;margin:40px auto;padding:0 24px}h1{font-size:36px;margin-bottom:10px}p{color:#becbc8;line-height:1.5}nav{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}button{font:inherit;border:1px solid #58736b;border-radius:8px;padding:9px 15px;background:#263a34;color:#edf0ea;cursor:pointer}button.active{background:#c9e7d7;color:#15362b}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:20px}article{background:#1c2929;border-radius:12px;overflow:hidden}article h2,article p{margin:14px 18px}img{width:100%;display:block}aside{border-left:3px solid #77978c;padding-left:18px;margin:30px 0}</style>
<h1>Four characters, now in Unity</h1><p>Still captures from the desktop player. These are Unity's converted materials, with the existing consultation room and assigned voices.</p>
<nav id="moods"></nav><main>'''+''.join(cards)+'''</main>
<aside><p>The desktop preview executable has moving reactions and “Play assigned voice” for each character:<br><code>unity/Builds/MetaHumanPreview/MetaHumanPreview.exe</code></p>
<p>The main game remains at <code>unity/Builds/Windows/AlexPrototype.exe</code>, or use the usual launcher for conversation services.</p>
<p>This is the first Unity port. Skin and hair shading differ from Unreal; strand-only buzz cut, stubble and eyelashes are not reproduced. Torso/hand acting and headset performance testing remain separate.</p></aside>
<script>const moods={neutral:'Neutral',angry:'Anger',crying:'Crying',afraid:'Fear',happy:'Happiness',sad:'Sadness',disgusted:'Disgust',speaking:'Speech + anger',body:'Seated pose','room-room':'In the room','room-crying':'Crying in the room'};for(const [key,label] of Object.entries(moods)){const b=document.createElement('button');b.textContent=label;b.className=key==='neutral'?'active':'';b.onclick=()=>{document.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('img').forEach(x=>x.src=x.dataset.person+'/'+key+'.png')};document.querySelector('nav').append(b)}</script>''',encoding='utf-8')
shutil.copy2(ROOT/'experiments/metahuman/exports/unity/validation.json',OUT/'verification.json')
print('http://127.0.0.1:8798/metahuman-unity/')
