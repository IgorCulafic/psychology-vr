"""Run the Unreal opening/playback smoke test against an isolated real bridge.

Uses two quiet generated PCM16 tones, not AI speech. Checks the native client's
HTTP/WAV/playback acknowledgements without occupying model VRAM.
"""
import argparse
import array
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import wave
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from alex_service import Bridge, make_handler, validate_reply


class FixtureBridge(Bridge):
    def generate(self, *args, **kwargs):
        return validate_reply({'segments': [
            {'text': 'This is the first playback check.', 'emotion': 'calm', 'intensity': .4,
             'gesture': 'none', 'voice_style': 'normal'},
            {'text': 'This is the second playback check.', 'emotion': 'sad', 'intensity': .6,
             'gesture': 'look_down', 'voice_style': 'subdued'}]})

    def synthesize(self, segment, audio_id):
        rate = 24000
        samples = array.array('h', (int(600 * math.sin(2 * math.pi * 330 * i / rate)) for i in range(rate)))
        with wave.open(str(self.runtime / (audio_id + '.wav')), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(samples.tobytes())
        return '/audio/' + audio_id + '.wav'

    def align_mouth(self, audio_id, text):
        return [{'start': 0., 'end': .9, 'value': 'D'}, {'start': .9, 'end': 1., 'value': 'X'}], 'fixture'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--editor', default=r'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe')
    parser.add_argument('--menu', action='store_true', help='Capture the initial menu without starting a conversation')
    args = parser.parse_args()
    runtime = ROOT / 'services/.runtime'
    config = json.loads((ROOT / 'services/config.example.json').read_text())
    config.update(tts_provider='none', session_log_dir=str(runtime / 'unreal-smoke-sessions'))
    bridge = FixtureBridge(config)
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    log = runtime / ('unreal-menu-check.log' if args.menu else 'unreal-smoke.log')
    if log.exists(): log.unlink()
    capture = ROOT / ('docs/generated/unreal-menu.png' if args.menu else 'docs/generated/unreal-room.png')
    if capture.exists(): capture.unlink()
    try:
        result = subprocess.run([args.editor, str(ROOT / 'unreal/PsychologyVR.uproject'),
            '/Game/Psychology/Consultation', '-game', '-nohmd', '-MenuPreview' if args.menu else '-PsychologySmoke',
            '-RenderOffscreen', '-unattended', '-nosplash', '-windowed', '-ResX=1280', '-ResY=720',
            '-PsychologyCapture=' + str(capture),
            '-BridgeUrl=http://127.0.0.1:' + str(server.server_port), '-abslog=' + str(log)],
            cwd=ROOT, timeout=1200)
        output = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        marker = 'PSYCHOLOGY_WORLD_READY patients=1' if args.menu else 'PSYCHOLOGY_SMOKE_OK'
        assert result.returncode == 0 and marker in output, 'Unreal validation failed; see ' + str(log)
        assert capture.exists(), 'Rendered capture was not saved'
        assert 'Failed to compile Material' not in output, 'Broken material; see ' + str(log)
        assert 'Default Material will be used in game' not in output, 'Material usage missing; see ' + str(log)
        if args.menu:
            assert not bridge.sessions, 'Menu preview must not start a patient session'
            print('Menu capture saved: ' + str(capture))
            return
        sessions = list(bridge.sessions.values())
        assert len(sessions) == 1, 'Expected one patient session'
        session = sessions[0]
        assert session.stream['completed_count'] == 2 and session.stream['closed'], session.stream
        assert len(session.history) == 2, 'Opening must commit one user/assistant pair'
        heard = json.loads(session.history[-1]['content'])['segments']
        assert len(heard) == 2 and 'second playback' in heard[-1]['text'], heard
        report = {'status': 'passed', 'completed_audio_segments': 2, 'history_committed': True,
                  'bridge': 'isolated scripted fixture', 'audio': 'PCM16 tones; not live AI or headset verification'}
        (ROOT / 'docs/generated/unreal-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
