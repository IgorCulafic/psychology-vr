"""Copy the installed Editor's URP settings without its sample project or caches."""
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'unity'
TEMPLATE = Path('C:/Program Files/Unity/Hub/Editor/6000.6.0f1/Editor/Data/Resources/PackageManager/ProjectTemplates/com.unity.template.urp-blank-17.2.1.tgz')
with tarfile.open(TEMPLATE) as archive:
    for member in archive.getmembers():
        prefix = 'package/ProjectData~/'
        if not member.isfile() or not member.name.startswith(prefix):
            continue
        relative = member.name[len(prefix):]
        if not (relative.startswith('ProjectSettings/') or relative.startswith('Assets/Settings')):
            continue
        target = (PROJECT / relative).resolve()
        if not target.is_relative_to(PROJECT.resolve()):
            raise RuntimeError('Unexpected template path')
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
manifest = {
    'dependencies': {
        'com.unity.inputsystem': '1.19.0',
        'com.unity.render-pipelines.universal': '17.6.0',
        'com.unity.ugui': '2.6.0',
        'com.unity.xr.management': '4.6.1',
        'com.unity.xr.openxr': '1.18.0',
        'com.unity.xr.interaction.toolkit': '3.6.0',
        'com.unity.modules.audio': '1.0.0',
        'com.unity.modules.animation': '1.0.0',
        'com.unity.modules.imgui': '1.0.0',
        'com.unity.modules.physics': '1.0.0',
        'com.unity.modules.jsonserialize': '1.0.0',
        'com.unity.modules.imageconversion': '1.0.0',
        'com.unity.modules.unitywebrequest': '1.0.0',
        'com.unity.modules.unitywebrequestaudio': '1.0.0',
        'com.unity.modules.xr': '1.0.0',
    }
}
(PROJECT / 'Packages').mkdir(exist_ok=True)
(PROJECT / 'Packages/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(PROJECT / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.0f1\n')
print('Created Unity project settings for 6000.6.0f1')
