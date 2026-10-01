"""Prepare one contributed voice pack without changing its original recordings.

Run with the project .venv Python, e.g. tools/prepare-voice-pack.py person_03.
Transcripts are automatic drafts; reference selection and listening follow later.
"""
import argparse
import csv
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

os.environ['HF_HUB_OFFLINE'] = '1'
import av
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from speech_language import latin_script

SLUGS = ['neutral_conversation', 'neutral_pronunciation', 'frustrated', 'angry',
         'sad', 'near_tears', 'anxious', 'happy', 'afraid', 'low_energy',
         'disgusted', 'relieved']


def decode(path):
    with av.open(str(path)) as source:
        stream = source.streams.audio[0]
        rate = stream.codec_context.sample_rate
        resampler = av.AudioResampler(format='fltp', layout='mono', rate=rate)
        chunks = []
        errors = []
        expected_seconds = float(stream.duration * stream.time_base) if stream.duration else None
        for packet in source.demux(stream):
            try:
                frames = packet.decode()
            except av.error.InvalidDataError:
                errors.append(dict(pts=packet.pts, duration=packet.duration,
                                   seconds=float(packet.pts * stream.time_base) if packet.pts is not None else None))
                continue
            for frame in frames:
                chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(None))
    audio = np.concatenate(chunks)
    if not audio.size or not np.isfinite(audio).all():
        raise ValueError(f'Invalid audio: {path}')
    if errors and (expected_seconds is None or any(e['seconds'] is None or
            e['seconds'] < expected_seconds - .15 for e in errors)):
        raise ValueError(f'Audio has invalid packets before its trailing boundary: {path}')
    return audio, rate, errors, expected_seconds


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('person')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--resume', action='store_true', help='Reuse completed matching files after an interrupted run')
    args = parser.parse_args()
    if not re.fullmatch(r'person_\d+', args.person):
        parser.error('Expected an anonymous speaker ID such as person_03')
    folder = ROOT / 'voices' / args.person
    sources = sorted(folder.glob('*.m4a'))
    if not sources:
        parser.error('No M4A files found')
    out = folder / 'prepared'
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error('Prepared folder already exists; refusing to overwrite reviewed work')
    out.mkdir(exist_ok=True)
    guide = (ROOT / 'docs/VOICE_RECORDING_SCRIPT_ME.md').read_text(encoding='utf-8')
    scripts = {int(n): re.search(r'^> ([^\n]+)', body, re.M).group(1)
               for n, body in re.findall(r'^## (\d+)[^\n]*\n(.*?)(?=^## |\Z)', guide, re.M | re.S)}
    model = WhisperModel(str(ROOT / '.cache/whisper/large-v3-turbo'),
                         device=args.device, compute_type='float16' if args.device == 'cuda' else 'int8',
                         cpu_threads=8, local_files_only=True)
    rows = json.loads((out / 'inventory.json').read_text(encoding='utf-8')) if args.resume and (out / 'inventory.json').exists() else []
    for source in sources:
        completed = next((r for r in rows if r['original'] == source.name), None)
        if completed:
            if hashlib.sha256(source.read_bytes()).hexdigest() != completed['original_sha256'] or not (out / completed['wav']).exists():
                raise ValueError(f'Changed or missing completed input/output: {source.name}')
            continue
        start = time.perf_counter()
        audio, rate, errors, expected_seconds = decode(source)
        ambient = source.stem.lower().startswith('ambient')
        number_match = re.match(r'^(\d{2})\b', source.stem)
        number = int(number_match[1]) if number_match else None
        if number is not None and number not in scripts:
            raise ValueError(f'Unknown script number: {source.name}')
        label = f'{number:02d}_{SLUGS[number-1]}' if number else re.sub(r'\W+', '_', source.stem.lower()).strip('_')
        target = out / (label + '.wav')
        if target.exists():
            raise ValueError(f'Duplicate output: {target}')
        peak = float(np.abs(audio).max())
        gain = 1.0 if ambient else min(10 ** (24/20), 10 ** (-3/20) / max(peak, 1e-9))
        sf.write(target, audio * gain, rate, subtype='PCM_16')
        segments = []
        if not ambient:
            detected, _ = model.transcribe(str(target), language='sr', beam_size=5,
                condition_on_previous_text=False, vad_filter=True, word_timestamps=True,
                initial_prompt='Razgovor na crnogorskom jeziku, latinicom.')
            segments = [dict(start=s.start, end=s.end, text=latin_script(s.text).strip(),
                words=[dict(start=w.start, end=w.end, word=latin_script(w.word), probability=w.probability)
                       for w in (s.words or [])]) for s in detected]
        text = ' '.join(s['text'] for s in segments)
        normalize = lambda t: re.sub(r'[^\w ]', '', latin_script(t).lower()).split()
        matches = sorted([(difflib.SequenceMatcher(None, normalize(text), normalize(t)).ratio(), n)
                          for n, t in scripts.items()], reverse=True) if text else []
        row = dict(original=source.name, original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   wav=target.name, duration_seconds=round(len(audio)/rate, 3), sample_rate=rate,
                   peak_dbfs=round(float(20*np.log10(max(peak, 1e-9))), 2),
                   rms_dbfs=round(float(20*np.log10(max(float(np.sqrt(np.mean(audio.astype('float64')**2))), 1e-9))), 2),
                   near_full_scale_percent=round(100*float(np.mean(np.abs(audio)>=.999)), 4),
                   script_number=number, detected_script=matches[0][1] if matches else None,
                   match_score=round(matches[0][0], 3) if matches else None,
                   transcript_status='not_transcribed_ambient' if ambient else 'automatic_draft_not_listening_verified',
                   text=text, segments=segments,
                   decode_errors=errors, container_duration_seconds=expected_seconds,
                   preparation=dict(format='mono PCM16 WAV', gain_db=round(float(20*np.log10(gain)), 3),
                                    processing='constant gain only; no denoising, pitch or timing changes'))
        write_json(target.with_suffix('.json'), row)
        rows.append(row)
        write_json(out / 'inventory.json', rows)
        print(json.dumps({k: row[k] for k in ['original', 'duration_seconds', 'script_number', 'detected_script', 'match_score']})
              + f' elapsed={time.perf_counter()-start:.1f}s', flush=True)
    with (out / 'file_mapping.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['original', 'prepared_wav', 'script_number', 'seconds', 'gain_db'])
        writer.writerows([r['original'], r['wav'], r['script_number'], r['duration_seconds'], r['preparation']['gain_db']] for r in rows)
    (out / 'transcripts_DRAFT.txt').write_text('AUTOMATIC DRAFTS - listening review pending.\n\n' +
        '\n\n'.join(r['wav'] + '\n' + r['text'] for r in rows) + '\n', encoding='utf-8')
    print('VOICE_PREPARATION_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
