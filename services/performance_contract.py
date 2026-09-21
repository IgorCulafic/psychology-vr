"""Bounded actor directions, independent of provider-specific speech tokens."""
import math
import re
import unicodedata

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
Return usually ONE segment with 1-2 short sentences, at most 45 spoken words total
unless the relationship state explicitly permits a fuller answer within its word budget.
Use a second segment only when the actual feeling or delivery changes within the reply.
Each segment is a spoken beat; emotion and intensity describe the feeling NOW, not a quoted memory.
Use the current emotional state as your starting point. Change gradually unless the player's words
provide a clear reason for a strong reaction. Never invent events to justify a cue.
Decide delivery from the meaning of the exchange, not an emotion keyword or a command from the player.
An ordinary factual answer can stay neutral even if it mentions anger, fear or crying.
Intensity: 0.15-0.35 subtle, 0.4-0.65 clearly readable, 0.7-0.85 strong, above 0.85 exceptional.
Frustrated means restrained objection; angry means direct confrontation. Sad means grief without
necessarily shedding tears; crying requires actually losing composure. Numb is withdrawn stillness,
not just a sad sentence. Relief is a partial easing, not instant happiness or complete recovery.
When reassurance follows an upsetting remark, the answer may start tense and then soften. Use two
short segments only if both beats are genuinely present; put each cue beside the words it belongs to.
Choose a supported gesture or none. Usually use none; avoid repeating the same gesture every turn.
For strong crying or panic prefer no extra gesture; the body preset already supplies the action.
Choose voice_style for delivery: tense for pressure, subdued for quiet withdrawal, hesitant for
hesitation, gentle for softened contact, normal otherwise. Do not label every anxious reply hesitant.
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
PATIENT_PERFORMANCE_PROMPT = """
Usually one spoken segment; use two only for a real change of feeling, not to pad the answer.
Use relationship word_limit. Emotion describes the present feeling, not quoted memories or player commands.
Frustrated is restrained objection; angry is confrontation; sad need not cry; crying is losing composure;
numb is withdrawn stillness; relief is partial easing, never recovery. Intensity .2 subtle, .5 clear,
.7-.85 strong, >.85 exceptional. Personal cruelty can justify a sharp change; ordinary questions cannot.
Gestures normally none; never add extra gestures to strong crying/panic. Voice: normal, subdued,
hesitant, tense or gentle as appropriate. Gaze listener engages; down/away withdraws; automatic follows posture.
transition_seconds usually .4-1; pause_before_seconds 0-.4; hold_after_seconds 0-.4.
gesture_at is a FRACTION of audio (0=start, .5=middle); gesture_duration_seconds usually .5-2.5.
Only text is spoken. No stage directions, control tags or joint angles in text. Control enums stay English.
"""


HIGGS_EMOTIONS = {'angry': 'anger', 'frustrated': 'bitterness', 'sad': 'sadness',
    'crying': 'sadness', 'despondent': 'helplessness', 'afraid': 'fear', 'panicked': 'fear',
    'anxious': 'fear', 'disgusted': 'disgust', 'ashamed': 'shame', 'guilty': 'shame',
    'happy': 'elation', 'hopeful': 'enthusiasm', 'relieved': 'relief', 'calm': 'contentment',
    'confused': 'confusion', 'surprised': 'surprise', 'skeptical': 'contemplation'}


def refine_delivery(segments,state,recent_gestures=()):
    """Keep semantic emotion choices; damp gratuitous motion and abrupt recovery."""
    result=[];previous=state.get('emotion','neutral');intensity=state.get('intensity',.3)
    used=list(recent_gestures[-2:])
    for source in segments:
        segment=dict(source);emotion=segment['emotion'];gesture=segment['gesture']
        if (gesture!='none' and gesture in used) or (emotion in ('crying','panicked','numb','despondent') and segment['intensity']>=.6):
            segment['gesture']='none'
        if gesture=='wipe_tear' and emotion not in ('crying','sad'):segment['gesture']='none'
        if emotion!=previous:
            # Let confrontation rise promptly; recovery/withdrawal settles slowly.
            settling=emotion in ('relieved','calm','sad','despondent','numb')
            floor=.95 if settling else .5
            segment['transition_seconds']=max(segment['transition_seconds'],floor)
        elif abs(segment['intensity']-intensity)>.25:
            segment['transition_seconds']=max(segment['transition_seconds'],.8)
        used.append(segment['gesture']);used=used[-2:]
        result.append(segment);previous=emotion;intensity=segment['intensity']
    return result


def speech_text(text,pronunciation=None):
    """TTS-only, explicit pronunciation aliases; original transcript is preserved."""
    text=unicodedata.normalize('NFC',text)
    for source,target in (pronunciation or {}).items():
        if not isinstance(source,str) or not source.strip() or not isinstance(target,str) or not target.strip() or len(source)>80 or len(target)>120 or re.search(r'[<>\[\]{}*`]',source+target):
            raise ValueError('Invalid pronunciation alias')
        text=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',lambda match:target,text)
    return re.sub(r'\s+',' ',text).strip()


def higgs_text(segment,pronunciation=None):
    emotion = HIGGS_EMOTIONS.get(segment['emotion'])
    tags = []
    # Mild unease should not become frightened speech or change the voice identity.
    threshold=.65 if segment['emotion']=='anxious' else .25
    if emotion and segment['intensity'] >= threshold:
        tags.append('<|emotion:' + emotion + '|>')
    # Preserve the preferred angry audition's single anger tag. No automatic shouting,
    # pitch shifting or nonverbal sobbing: those can alter identity and intelligibility.
    if segment['emotion'] == 'numb':
        tags.append('<|prosody:expressive_low|>')
    if segment['voice_style'] == 'hesitant':
        tags.append('<|prosody:speed_slow|>')
    return ''.join(tags) + speech_text(segment['text'],pronunciation)
