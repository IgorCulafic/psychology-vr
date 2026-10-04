"""Save the selected Round 1 voice recipes without changing game voice routing."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'voices/igor_2026-10-03/remaining-voice-repairs'
LEDGER = REVIEW.parent / 'emotion-validation/review_decisions.json'
PRESETS = {
    'person_02-anger': 'voices/person_02/prepared/preferred_anger.json',
    'person_03-anger': 'voices/person_03/prepared/preferred_anger.json',
    'igor-sadness': 'voices/igor_2026-10-03/cleaned/preferred_sadness.json',
    'igor-happiness': 'voices/igor_2026-10-03/cleaned/preferred_happiness.json',
    'igor-disgust': 'voices/igor_2026-10-03/cleaned/preferred_disgusted.json',
}

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def relative(path):
    return path.relative_to(ROOT).as_posix()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feedback', type=Path)
    args = parser.parse_args()
    feedback = read(args.feedback)
    assert feedback['round'] == 'repair-round-1'
    choices = feedback['reviews']
    rows = read(REVIEW / 'results.json')
    selections = {}
    # Validate all selections and assets before updating any preference.
    for group in PRESETS:
        choice = choices[group]['choice']
        assert choice in ('A is best', 'B is best'), (group, choice)
        selected = sorted([r for r in rows if r['group'] == group and r['variant'] == choice[0]], key=lambda r: r['index'])
        assert selected, group
        for row in selected:
            assert digest(REVIEW / row['file']) == row['sha256']
            assert digest(ROOT / row['reference']) == row['reference_sha256']
            assert read((ROOT / row['reference']).with_suffix('.json'))['text'] == row['reference_text']
        selections[group] = selected
    for speaker in ('person_02', 'person_03'):
        variant = choices[speaker + '-transition']['choice'][0]
        assert variant == selections[speaker + '-anger'][0]['variant']
        assert (REVIEW / f'{speaker}-transition-{variant}.wav').is_file()
    for speaker in ('person_02', 'person_03', 'igor_2026-10-03'):
        assert choices[speaker + '-pronunciation']['choice'] == 'A is best'

    archive = REVIEW / 'feedback' / digest(args.feedback)
    archive.mkdir(parents=True, exist_ok=True)
    feedback_path = archive / args.feedback.name
    shutil.copy2(args.feedback, feedback_path)
    if not (archive / 'previous-review-decisions.json').exists():
        shutil.copy2(LEDGER, archive / 'previous-review-decisions.json')
    approval = {
        'status': 'approved_by_user_for_use', 'approval_date': '2026-10-04',
        'approval_quote': 'There, I think this is good enough now.',
        'feedback_source': relative(feedback_path), 'feedback_sha256': digest(feedback_path),
        'feedback_saved_at': feedback['saved_at'],
    }
    ledger = read(LEDGER)
    for group, selected in selections.items():
        path = ROOT / PRESETS[group]
        preset = read(path)
        backup = archive / (group + '-previous-preset.json')
        if not backup.exists():
            shutil.copy2(path, backup)
        row = selected[0]
        # Keep a canonical existing reference when it is byte-identical.
        reference = ROOT / preset['reference']
        if digest(reference) != row['reference_sha256']:
            reference = ROOT / row['reference']
        if 'emotion-validation' in reference.parts:
            reference = path.parent / 'approved-references' / (group + '.wav')
            reference.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT / row['reference'], reference)
            shutil.copy2((ROOT / row['reference']).with_suffix('.json'), reference.with_suffix('.json'))
        samples = []
        for item in selected:
            target = path.parent / 'auditions' / item['file']
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(REVIEW / item['file'], target)
            samples.append({**item, 'audio': relative(target), 'file': relative(target)})
        for key in ('consistency_review', 'transition_review'):
            if key in preset:
                preset.setdefault('review_history', []).append({key: preset.pop(key)})
        preset.update(approval)
        preset.update({
            'default_variant': row['variant'], 'user_choice': choices[group]['choice'],
            'accepted_variants': [row['variant']], 'default_reason': 'explicit user selection after repair',
            'temperature': row['temperature'], 'higgs_quantization': 'bf16',
            'top_p': .95, 'top_k': 50, 'seed': 42,
            'reference': relative(reference), 'reference_transcript': relative(reference.with_suffix('.json')),
            'reference_sha256': row['reference_sha256'], 'reference_text': row['reference_text'],
            'emotion_tag': ''.join(re.findall(r'<\|emotion:[^|]+\|>', row['tag'])) or None,
            'prosody_tag': ''.join(re.findall(r'<\|prosody:[^|]+\|>', row['tag'])) or None,
            'tts_script': 'latin', 'synthesis_mode': row['mode'],
            'sentence_gap_seconds': .38 if row['mode'] == 'sentences' else 0,
            'generation_recipe': {'tag': row['tag'], 'mode': row['mode'], 'max_new_tokens': 900,
                'quality_check': 'speech_audio.checked_synthesis', 'retry_seed': 43,
                'retry_temperature': min(row['temperature'], .45), 'recovery_gap_seconds': .25},
            'audition_audio': samples[0]['audio'], 'audition_sha256': samples[0]['sha256'],
            'audition_display_label': row['variant'] + ' · ' + row['title'],
            'approved_candidates': samples, 'user_feedback': choices[group]['choice'],
            'user_notes': choices[group]['notes'], 'must_fix_before_runtime': False,
            'active_in_game': False,
            'note': 'Approved speaker-specific repair recipe. Patient voice routing remains pending.',
            'repair_review': {**approval, **choices[group]},
        })
        # Listening approval does not certify a draft reference transcription.
        meta = read(reference.with_suffix('.json'))
        preset['reference_transcript_status'] = meta.get('reference_transcript_status', meta.get('transcript_status', meta.get('status', 'unchanged_from_source')))
        if row['speaker'] == 'person_03':
            preset['reference_transcript_status'] = 'draft_used_in_approved_audition'
        if row['speaker'] in ('person_02', 'person_03'):
            speaker = row['speaker']
            source = REVIEW / f'{speaker}-transition-{row["variant"]}.wav'
            target = path.parent / 'auditions' / source.name
            shutil.copy2(source, target)
            preset['transition_review'] = {**approval, **choices[speaker + '-transition'],
                                           'audio': relative(target), 'sha256': digest(target)}
        write(path, preset)
        state = ledger['speakers'][row['speaker']]
        state.setdefault('repair_selections', {})[group] = {**approval, **choices[group], 'preference_file': relative(path)}
        if group.endswith('-anger'):
            state['transitions'] = preset['transition_review']
            state['consistency']['anger'] = preset['repair_review']
        elif group in ('igor-sadness', 'igor-happiness'):
            state['consistency'][group.split('-')[1]] = preset['repair_review']
        else:
            state['emotions']['disgusted'].update(status=approval['status'], default_variant=row['variant'], latest_review=preset['repair_review'])

    for speaker in ('person_02', 'person_03', 'igor_2026-10-03'):
        state = ledger['speakers'][speaker]
        state['pronunciation_review'] = {**approval, **choices[speaker + '-pronunciation'], 'tts_script': 'latin'}
        folder = ROOT / 'voices' / speaker / ('cleaned' if speaker.startswith('igor') else 'prepared')
        write(folder / 'preferred_pronunciation.json', {
            **state['pronunciation_review'], 'person': speaker,
            'kind': 'text_input_preference', 'new_dialogue_wording': 'nisam',
            'note': 'Latin spelling retained. Listening preference is not a guarantee of exact č/ć pronunciation.',
        })
        write(folder / 'emotion_review.json', state)
    for item in ledger['refinement_queue']:
        if item['speaker'] != 'person_01':
            item.update(status='resolved_by_user_approval', resolution=approval)
    ledger['latest_repair_approval'] = approval
    write(LEDGER, ledger)
    write(REVIEW / 'approval.json', {**approval, 'selections': choices, 'active_in_game': False})
    continuation = read(REVIEW / 'continuation.json')
    continuation.update(status='approved_by_user_for_use', approval=approval)
    write(REVIEW / 'continuation.json', continuation)
    print('Saved five delivery presets, two transitions and three Latin-text preferences. Game routing unchanged.')

if __name__ == '__main__':
    main()
