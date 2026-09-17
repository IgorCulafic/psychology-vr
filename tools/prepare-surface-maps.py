"""Preserve source material channels for URP; no new asset downloads required."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'unity/Assets/PsychologyVR/Art/Environment'
OUT = ART / 'Textures/SurfaceDetail'
OUT.mkdir(parents=True, exist_ok=True)
records = []
for source in sorted((ROOT / '.cache/assets/polyhaven').glob('*/*.gltf')):
    data = json.loads(source.read_text(encoding='utf-8'))
    for index, material in enumerate(data.get('materials', [])):
        pbr = material.get('pbrMetallicRoughness', {})
        ref = pbr.get('metallicRoughnessTexture')
        if not ref:
            continue
        uri = data['images'][data['textures'][ref['index']]['source']]['uri']
        image = Image.open(source.parent / uri).convert('RGB')
        red, green, blue = image.split()
        arm = '_arm_' in uri
        metallic = blue.point(lambda v: round(v * pbr.get('metallicFactor', 1)))
        smoothness = green.point(lambda v: 255 - round(v * pbr.get('roughnessFactor', 1)))
        occlusion = red if arm else Image.new('L', image.size, 255)
        name = f'{source.parent.name}_mat_{index}'
        target = OUT / f'{name}_metal_smooth.png'
        Image.merge('RGBA', (metallic, occlusion, Image.new('L', image.size, 0), smoothness)).save(target)
        records.append({'material': name, 'map': target.relative_to(ROOT / 'unity').as_posix(), 'occlusion': arm})

for material, file in [('Room_Oak', 'wood_floor_rough.jpg'), ('Room_Plaster', 'white_plaster_02_rough.jpg'), ('Room_Sage', 'white_plaster_02_rough.jpg')]:
    rough = Image.open(ART / 'Textures' / file).convert('L')
    target = OUT / f'{material}_metal_smooth.png'
    Image.merge('RGBA', (Image.new('L', rough.size, 0), Image.new('L', rough.size, 255), Image.new('L', rough.size, 0), rough.point(lambda v: 255-v))).save(target)
    records.append({'material': material, 'map': target.relative_to(ROOT / 'unity').as_posix(), 'occlusion': False})
(ART / 'surface-detail.json').write_text(json.dumps({'materials': records}, indent=2), encoding='utf-8')
print(f'Prepared {len(records)} surface maps from existing source textures.')
