"""Build self-contained runtime voice packs from the approved listening presets."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENTS = {'ivan-work-exhaustion': 'igor_2026-10-03',
               'stefan-fire-witness': 'person_01',
               'nikola-bereavement': 'person_02', 'alex-earthquake': 'person_03'}

def main():
    cast = {'version': 1, 'precision': 'bf16', 'scenarios': ASSIGNMENTS, 'speakers': {}}
    for speaker in ASSIGNMENTS.values():
        folder = ROOT / 'voices' / speaker / ('cleaned' if speaker.startswith('igor') else 'prepared')
        output = ROOT / 'voices/runtime' / speaker
        output.mkdir(parents=True, exist_ok=True)
        recipes = {}
        for path in sorted(folder.glob('preferred_*.json')):
            preset = json.loads(path.read_text(encoding='utf-8'))
            if preset.get('kind') == 'text_input_preference': continue
            if preset.get('must_fix_before_runtime'): raise ValueError('Unapproved repair: ' + str(path))
            recipes[path.stem.removeprefix('preferred_')] = (preset, path)
        if 'neutral' not in recipes:
            # Neutral uses the same recorded reference as the reviewed transitions.
            source = ROOT / f'voices/igor_2026-10-03/emotion-validation/{speaker}/references/neutral.wav'
            if not source.exists(): raise FileNotFoundError(source)
            recipes['neutral'] = ({'reference': source.relative_to(ROOT).as_posix(),
                                  'temperature': .6, 'emotion_tag': None}, None)
        manifest = {'speaker': speaker, 'precision': 'bf16', 'recipes': {}}
        for emotion, (preset, source_preset) in recipes.items():
            reference = ROOT / preset['reference']
            sha = hashlib.sha256(reference.read_bytes()).hexdigest()
            if preset.get('reference_sha256') and sha != preset['reference_sha256']:
                raise ValueError('Reference changed: ' + str(reference))
            target = output / (emotion + '.wav')
            shutil.copy2(reference, target)
            transcript = json.loads(reference.with_suffix('.json').read_text(encoding='utf-8-sig'))
            if preset.get('reference_text') and transcript['text'] != preset['reference_text']:
                raise ValueError('Transcript changed: ' + str(reference))
            target.with_suffix('.json').write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding='utf-8')
            recipe = preset.get('generation_recipe', {})
            manifest['recipes'][emotion] = {
                'reference': target.relative_to(ROOT).as_posix(), 'reference_sha256': sha,
                'reference_text': transcript['text'],
                'tag': (preset.get('emotion_tag') or '') + (preset.get('prosody_tag') or ''),
                'temperature': preset.get('temperature', .6), 'top_p': preset.get('top_p', .95),
                'top_k': preset.get('top_k', 50), 'seed': preset.get('seed', 42),
                'retry_seed': recipe.get('retry_seed', 43),
                'retry_temperature': recipe.get('retry_temperature', min(preset.get('temperature', .6), .5)),
                'max_new_tokens': recipe.get('max_new_tokens', 900),
                'mode': preset.get('synthesis_mode', 'whole'),
                'sentence_gap_seconds': preset.get('sentence_gap_seconds', 0),
                'source_preset': source_preset.relative_to(ROOT).as_posix() if source_preset else None,
                'tts_script': 'latin',
            }
        manifest_path = output / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        cast['speakers'][speaker] = manifest_path.relative_to(ROOT).as_posix()
    (ROOT / 'voices/cast.json').write_text(json.dumps(cast, indent=2) + '\n', encoding='utf-8')
    print('Built four scenario voice packs with approved references and generation settings.')

if __name__ == '__main__': main()
