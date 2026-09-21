"""Capture real conversation performances plus a labelled timing fixture for Unity.

Start tools/launch.ps1 -NoGame first. Output and voice files remain private/local.
Then launch the built player with --desktop --performance-replay <absolute output>.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from alex_service import Bridge, validate_reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'services/.runtime/performance/replies.json')
    args = parser.parse_args()
    config = json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8'))
    if config['tts_provider'] != 'higgs':
        parser.error('Select Higgs in config.local.json for this expressive speech check.')
    bridge = Bridge(config)
    base = 'http://127.0.0.1:' + str(config['port'])
    session = bridge.post_json(base+'/session', {}, 20)['session_id']
    result = {'turns': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    for name, text in [
        ('opening-concern', 'Šta vam je najteže otkako ste ostali bez doma?'),
        ('dismissal', 'Prestanite da dramatizujete. Nije me briga koliko vam je teško; samo prestanite da se žalite.'),
        ('repair', 'Izvinite, to što sam rekao bilo je ružno i nepravedno. Želim da vas saslušam, bez požurivanja.'),
    ]:
        reply = bridge.post_json(base+'/turn', {'session_id':session, 'text':text}, 240)
        result['turns'].append(dict(name=name, source='live-qwen-higgs', prompt=text, reply=reply))
        save()
        print(name, json.dumps([{k:s[k] for k in ('text','emotion','intensity','gesture')} for s in reply['segments']], ensure_ascii=False), flush=True)

    # A known two-beat fixture exercises strong crying, recovery and timed gesture
    # even when a believable live conversation never calls for those particular cues.
    fixture = validate_reply({'segments':[
        dict(text='Teško mi je da pričam o tome. Treba mi malo vremena.', emotion='crying',
             intensity=.95, gesture='none', voice_style='subdued', gaze='down',
             transition_seconds=.8, pause_before_seconds=.4, hold_after_seconds=.5),
        dict(text='Hvala što ste ostali. Mogu da pokušam još jednom.', emotion='relieved',
             intensity=.5, gesture='nod', voice_style='gentle', gaze='listener',
             transition_seconds=1.2, pause_before_seconds=.3, hold_after_seconds=.4,
             gesture_at=.4, gesture_duration_seconds=1.2),
    ]})
    for index, segment in enumerate(fixture):
        audio_id = uuid.uuid4().hex
        segment['audio_url'] = bridge.synthesize(segment, audio_id)
        segment['segment_id'] = 'controlled-transition-' + str(index)
        segment['mouth_cues'], segment['lip_sync_source'] = bridge.align_mouth(audio_id, segment['text'])
    result['turns'].append(dict(name='controlled-transition', source='authored-mechanical-fixture-higgs',
                                reply=dict(segments=fixture)))
    save()
    print('PERFORMANCE_CAPTURE_OK', args.output, flush=True)


if __name__ == '__main__':
    main()
