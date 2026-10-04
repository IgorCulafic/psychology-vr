"""Detect failed speech audio and make one bounded regeneration attempt.

This checks audio activity, not whether every word was spoken. Never repair an
apparently incomplete response by trimming its silent tail and publishing it.
"""
import numpy as np
from streaming_turns import sentence_segments


def audio_quality(audio, rate):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    seconds = len(audio) / rate
    if not len(audio) or not np.isfinite(audio).all():
        return {'ok': False, 'seconds': seconds, 'issues': ['empty or non-finite audio']}
    frame = max(1, round(rate * .02))
    frames = np.pad(audio, (0, (-len(audio)) % frame)).reshape(-1, frame)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    active = np.flatnonzero(rms > max(10 ** (-50 / 20), float(rms.max()) * .01))
    issues = []
    if not len(active):
        return {'ok': False, 'seconds': seconds, 'issues': ['no audible speech activity']}
    leading = active[0] * .02
    trailing = max(0., seconds - (active[-1] + 1) * .02)
    longest_gap = max(0., (float(np.diff(active).max()) - 1) * .02) if len(active) > 1 else 0.
    if seconds > 35: issues.append('overlong audio')
    if seconds < .2: issues.append('too short')
    if leading > 3: issues.append('long silent opening')
    if trailing > 3: issues.append('long silent ending')
    if longest_gap > 3: issues.append('long internal silence')
    return {'ok': not issues, 'seconds': round(seconds, 3), 'leading_seconds': round(leading, 3),
            'trailing_seconds': round(trailing, 3), 'longest_gap_seconds': round(longest_gap, 3), 'issues': issues}


def checked_synthesis(segment, render, rate):
    """render(segment, retry) returns a mono waveform; at most four retry calls."""
    audio = np.asarray(render(segment, False), dtype=np.float32).reshape(-1)
    first = audio_quality(audio, rate)
    if first['ok']:
        return audio, {'regenerated': False, 'quality': first}
    parts = sentence_segments([segment])
    if len(parts) > 4:
        raise ValueError('Failed speech audio; response exceeds bounded regeneration budget')
    clips = []
    for part in parts:
        retry = np.asarray(render(part, True), dtype=np.float32).reshape(-1)
        quality = audio_quality(retry, rate)
        if not quality['ok']:
            raise ValueError('Speech regeneration failed: ' + ', '.join(quality['issues']))
        if clips: clips.append(np.zeros(round(.25 * rate), dtype=np.float32))
        clips.append(retry)
    combined = np.concatenate(clips)
    final = audio_quality(combined, rate)
    if not final['ok']:
        raise ValueError('Combined speech regeneration failed: ' + ', '.join(final['issues']))
    return combined, {'regenerated': True, 'failed_quality': first, 'sentences': len(parts), 'quality': final}
