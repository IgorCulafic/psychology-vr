"""Choose a saved hardware profile without starting models or changing its template."""
import argparse
import json
from pathlib import Path
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
PROFILES=('rtx3080','rtx4090')


def profile_config(profile,root=ROOT):
    if profile not in PROFILES:raise ValueError('Choose rtx3080 or rtx4090')
    path=Path(root)/f'services/config.{profile}.json'
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config,dict) or config.get('hardware_profile')!=profile:
        raise ValueError('The saved hardware profile is invalid')
    return config


def select_profile(profile,root=ROOT):
    root=Path(root)
    config=profile_config(profile,root)
    path=root/'services/config.local.json'
    if path.exists():
        backup=root/'services/.runtime/config-backups'/f'hardware-{time.time_ns()}-{uuid.uuid4().hex}.json'
        backup.parent.mkdir(parents=True,exist_ok=True)
        with backup.open('xb') as handle:
            handle.write(path.read_bytes())
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
    return config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',choices=PROFILES)
    parser.add_argument('--check',action='store_true',help='Validate the profile without changing any files')
    args=parser.parse_args()
    config=profile_config(args.profile) if args.check else select_profile(args.profile)
    print('Selected' if not args.check else 'Available',args.profile,':',config['dialogue_model'],
          '/',config['tts_provider'],'/',config['conversation_language'])


if __name__=='__main__':main()
