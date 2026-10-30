"""Copy explicitly approved, transcripted audition clips into exact-line playback.

Reference passages and unreviewed variants are not promoted to patient answers.
The library never changes generated wording or chooses a line by similarity.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'services'))
from speech_reuse import wav_duration, text_key
from voice_cast import VoiceCast


def build(root=ROOT):
    root = Path(root).resolve()
    cast = VoiceCast(root)
    target = root/'voices/recorded'
    clips = []; seen = set()
    emotions = dict(anger='angry', sadness='sad', happiness='happy', low_energy='despondent')
    for scenario, speaker in cast.scenarios.items():
        for name, recipe in cast.speakers[speaker].items():
            preset_name = recipe.get('source_preset')
            if not preset_name:
                continue
            preset_path = (root/preset_name).resolve()
            if not preset_path.is_relative_to(root/'voices') or not preset_path.is_file():
                continue
            preset = json.loads(preset_path.read_text(encoding='utf-8'))
            if preset.get('status') != 'approved_by_user_for_use' or preset.get('person') != speaker:
                continue
            accepted = preset.get('accepted_variants', [preset.get('default_variant')])
            for candidate in preset.get('approved_candidates', []):
                if candidate.get('variant') not in accepted or candidate.get('quality', {}).get('ok') is not True:
                    continue
                source = (root/candidate.get('audio', candidate.get('file', ''))).resolve()
                if not source.is_relative_to(root/'voices') or not source.is_file():
                    continue
                data = source.read_bytes(); sha = hashlib.sha256(data).hexdigest()
                if sha != candidate.get('sha256'):
                    raise ValueError('Approved audition checksum changed: '+str(source))
                wav_duration(data)
                emotion = emotions.get(name, name)
                key = (scenario, emotion, text_key(candidate['text']))
                if key in seen:
                    continue
                seen.add(key)
                destination = target/speaker/(sha+'.wav')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                clips.append(dict(scenario_id=scenario, speaker=speaker, emotion=emotion,
                    text=candidate['text'], audio=destination.relative_to(root).as_posix(),
                    sha256=sha, approved=True, provenance=preset_name))
    if not clips:
        raise ValueError('No approved audition clips available; existing library was preserved')
    target.mkdir(parents=True, exist_ok=True)
    (target/'manifest.json').write_text(json.dumps(dict(version=1, clips=clips),
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return clips


if __name__ == '__main__':
    clips = build()
    print('Prepared '+str(len(clips))+' exact recorded lines. New wording still uses live synthesis.')
