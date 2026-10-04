"""Run in Blender background mode; inspect downloaded facial rigs without editing them."""
import bpy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'Assets/CharacterCandidates/Microsoft-Rocketbox'
report = []
for path in sorted(BASE.glob('Assets/Avatars/Adults/*/Export/*_facial.fbx')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    item = {'file': str(path.relative_to(BASE)), 'meshes': [], 'armatures': []}
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            keys = obj.data.shape_keys
            shapes = []
            if keys:
                base = keys.key_blocks[0]
                for key in list(keys.key_blocks)[1:]:
                    moved = sum((v.co - base.data[i].co).length_squared > 1e-12 for i, v in enumerate(key.data))
                    shapes.append({'name': key.name, 'moved_vertices': moved})
            item['meshes'].append({'name': obj.name, 'vertices': len(obj.data.vertices),
                                  'triangles': sum(len(p.vertices)-2 for p in obj.data.polygons),
                                  'shapes': shapes})
        elif obj.type == 'ARMATURE':
            item['armatures'].append({'name': obj.name, 'bones': [b.name for b in obj.data.bones]})
    report.append(item)
    print('AUDIT', path.name, 'bones', sum(len(a['bones']) for a in item['armatures']),
          'shapes', sum(len(m['shapes']) for m in item['meshes']), flush=True)
(BASE/'rig-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
