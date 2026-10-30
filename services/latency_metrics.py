"""Preparation-only speech schedule; never an assertion of audible playback."""
import math


def playback_schedule(segments):
    rows = []
    previous_end = previous_hold = 0.
    for index, segment in enumerate(segments):
        ready = segment['ready_ms'] / 1000
        duration = segment['audio_duration_seconds']
        pause = segment.get('pause_before_seconds', 0.)
        hold = segment.get('hold_after_seconds', 0.)
        values = (ready, duration, pause, hold)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Invalid speech preparation timing')
        expected = previous_end + previous_hold
        start = max(ready, expected) + pause
        wait = max(0., ready - expected) if index else 0.
        rows.append(dict(index=index, ready_seconds=round(ready,3),
            predicted_start_seconds=round(start,3), duration_seconds=round(duration,3),
            extra_preparation_wait_seconds=round(wait,3),
            speech_preparation_ms=segment.get('speech_preparation_ms'),
            alignment_preparation_ms=segment.get('alignment_preparation_ms'),
            speech_source=segment.get('speech_source','unknown')))
        previous_end, previous_hold = start + duration, hold
    return rows
