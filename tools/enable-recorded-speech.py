"""Enable exact-line reuse without changing dialogue, precision or GPU layers."""
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def enable(root=ROOT):
    root = Path(root)
    manifest = root/'voices/recorded/manifest.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not data.get('clips'):
        raise ValueError('Install the recorded-speech patch with its voice library first')
    path = root/'services/config.local.json'
    original = path.read_bytes()
    config = json.loads(original.decode('utf-8-sig'))
    if config.get('tts_provider') != 'higgs':
        raise ValueError('This optimization is for the existing Higgs cloned voices')
    config.update(speech_cache_enabled=True, recorded_speech_enabled=True, speech_cache_max_mib=256)
    directory = root/'services/.runtime/config-backups'
    directory.mkdir(parents=True, exist_ok=True)
    (directory/f'recorded-speech-{time.time_ns()}.json').write_bytes(original)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)
    return len(data['clips'])


if __name__ == '__main__':
    count = enable()
    print(f'Enabled {count} recorded lines and a 256 MiB exact speech/lip-sync cache.')
    print('Restart normally. New answers still need live synthesis; 15 seconds is not verified.')
