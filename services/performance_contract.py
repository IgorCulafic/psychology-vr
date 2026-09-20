"""Bounded actor directions, independent of provider-specific speech tokens."""
import math

GAZES = ('automatic', 'listener', 'down', 'away')
TIMING_DEFAULTS = {'transition_seconds': .65, 'pause_before_seconds': 0.,
                   'hold_after_seconds': .2, 'gesture_at': 0., 'gesture_duration_seconds': 2.5}
TIMING_LIMITS = {'transition_seconds': (.15, 2.), 'pause_before_seconds': (0., 1.5),
                 'hold_after_seconds': (0., 1.5), 'gesture_at': (0., .85),
                 'gesture_duration_seconds': (.3, 4.)}
FIELDS = ('text', 'emotion', 'intensity', 'gesture', 'voice_style', 'gaze', *TIMING_DEFAULTS)


def directions(segment):
    result = {'gaze': segment.get('gaze') if segment.get('gaze') in GAZES else 'automatic'}
    for name, default in TIMING_DEFAULTS.items():
        value = segment.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(name + ' must be a finite number')
        low, high = TIMING_LIMITS[name]
        result[name] = min(high, max(low, value))
    return result


PERFORMANCE_PROMPT = """
Direct a believable seated performance, never a demonstration of every emotion.
Return usually ONE segment with 1-2 short sentences, at most 45 spoken words total.
Use a second segment only when the actual feeling or delivery changes within the reply.
Each segment is a spoken beat; emotion and intensity describe the feeling NOW, not a quoted memory.
Use the current emotional state as your starting point. Change gradually unless the player's words
provide a clear reason for a strong reaction. Never invent events to justify a cue.
Choose a supported gesture or none. Usually use none; avoid repeating the same gesture every turn.
Gaze: automatic respects the emotional posture, listener seeks contact, down withdraws, away averts.
transition_seconds is the blend into this beat (typically 0.4-1.0).
pause_before_seconds is a short silent reaction before speaking (usually 0-0.4).
gesture_at is a FRACTION of this segment's audio duration (0=start, 0.5=midpoint),
and gesture_duration_seconds limits its duration. No word-level precision is implied.
hold_after_seconds is a brief pause after speaking; the emotion persists into listening and the next turn.
Do not specify joint angles, invented animations, or stage directions in text.
Only text is spoken. All direction fields are machine controls, never dialogue.
Keep cues in English enum values even when speech is in another language.
"""


# Only these trusted adapter tokens can reach Higgs. Model-produced text cannot contain tags.
HIGGS_EMOTIONS = {'angry': 'anger', 'frustrated': 'bitterness', 'sad': 'sadness',
    'crying': 'sadness', 'despondent': 'helplessness', 'afraid': 'fear', 'panicked': 'fear',
    'anxious': 'fear', 'disgusted': 'disgust', 'ashamed': 'shame', 'guilty': 'shame',
    'happy': 'elation', 'hopeful': 'enthusiasm', 'relieved': 'relief', 'calm': 'contentment',
    'confused': 'confusion', 'surprised': 'surprise', 'skeptical': 'contemplation'}


def higgs_text(segment):
    emotion = HIGGS_EMOTIONS.get(segment['emotion'])
    tags = []
    if emotion and segment['intensity'] >= .25:
        tags.append('<|emotion:' + emotion + '|>')
    # Preserve the preferred angry audition's single anger tag. No automatic shouting,
    # pitch shifting or nonverbal sobbing: those can alter identity and intelligibility.
    if segment['emotion'] == 'numb':
        tags.append('<|prosody:expressive_low|>')
    if segment['voice_style'] == 'hesitant':
        tags.append('<|prosody:speed_slow|>')
    return ''.join(tags) + segment['text']
