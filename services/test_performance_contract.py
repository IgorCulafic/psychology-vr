import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from alex_service import Bridge, ContractError, StaleTurn, validate_reply, SEGMENT_SCHEMA
from higgs_service import make_handler
from performance_contract import FIELDS, higgs_text


def beat(**changes):
    value = dict(text='Nijesam očekivao da ćete to reći.', emotion='angry', intensity=.8,
                 gesture='none', voice_style='tense')
    value.update(changes)
    return value


class PerformanceTests(unittest.TestCase):
    def test_old_segments_receive_safe_timing_defaults(self):
        result = validate_reply({'segments':[beat()]})[0]
        self.assertEqual(set(result), set(FIELDS))
        self.assertEqual(result['gaze'], 'automatic')
        self.assertEqual(result['gesture_at'], 0)
        self.assertEqual(result['transition_seconds'], .65)

    def test_timing_clamps_and_nonfinite_values_fail(self):
        result = validate_reply({'segments':[beat(pause_before_seconds=100,gesture_at=-4,gaze='ceiling')]})[0]
        self.assertEqual(result['pause_before_seconds'], 1.5)
        self.assertEqual(result['gesture_at'], 0)
        self.assertEqual(result['gaze'], 'automatic')
        for value in [float('nan'),float('inf'),True,'soon']:
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_reply({'segments':[beat(gesture_at=value)]})

    def test_preferred_anger_has_only_the_auditioned_emotion_token(self):
        value = validate_reply({'segments':[beat()]})[0]
        self.assertEqual(higgs_text(value), '<|emotion:anger|>'+value['text'])
        self.assertEqual(higgs_text(beat(emotion='neutral',voice_style='normal')),value['text'])
        with self.assertRaises(ContractError):
            validate_reply({'segments':[beat(text='<|style:shouting|>Hello')]})

    def test_prompt_localization_and_history_preserve_performance_but_not_audio(self):
        config = json.loads(Path(__file__).with_name('config.example.json').read_text())
        config.update(tts_provider='none',dialogue_provider='llama.cpp',conversation_language='cnr')
        bridge = Bridge(config)
        captured = {}
        def fake_post(url, body, timeout):
            captured.update(body)
            return {'choices':[{'message':{'content':json.dumps({'segments':[beat(gesture_at=.5,gaze='away')]})}}]}
        bridge.post_json = fake_post
        key = bridge.new_session()['session_id']
        opening = bridge.turn(key,'',True)
        self.assertIn('smirim',opening['segments'][0]['text'])
        reply = bridge.turn(key,'Kako se osjećate?')
        self.assertEqual(reply['segments'][0]['gesture_at'], .5)
        self.assertIn('Montenegrin', captured['messages'][0]['content'])
        self.assertIn('FRACTION', captured['messages'][0]['content'])
        memory = json.loads(bridge.sessions[key].history[-1]['content'])['segments'][0]
        self.assertEqual(memory['gaze'],'away')
        self.assertNotIn('audio_url',memory)
        self.assertEqual(bridge.sessions[key].emotion,'angry')
        self.assertEqual(set(SEGMENT_SCHEMA['properties']['segments']['items']['required']),set(FIELDS))

    def test_interrupt_during_synthesis_cannot_publish_audio_or_performance(self):
        config = json.loads(Path(__file__).with_name('config.example.json').read_text())
        bridge=Bridge(config)
        import tempfile
        with tempfile.TemporaryDirectory(dir=bridge.runtime) as folder:
            bridge.runtime=Path(folder)
            key=bridge.new_session()['session_id']
            started=threading.Event();release=threading.Event();errors=[]
            bridge.generate=lambda *args:[beat(gesture='wipe_tear',gesture_at=.5)]
            def slow(segment,audio_id):
                started.set();release.wait(3)
                (bridge.runtime/(audio_id+'.wav')).write_bytes(b'late audio')
                return '/audio/'+audio_id+'.wav'
            bridge.synthesize=slow
            def run():
                try:bridge.turn(key,'Hello')
                except Exception as exc:errors.append(exc)
            worker=threading.Thread(target=run);worker.start()
            self.assertTrue(started.wait(2))
            bridge.invalidate(key,reset=True);release.set();worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertIsInstance(errors[0],StaleTurn)
            self.assertEqual(list(bridge.runtime.iterdir()),[])
            self.assertEqual(bridge.sessions[key].history,[])
            self.assertEqual(bridge.sessions[key].emotion,'anxious')


class SpeechHttpTests(unittest.TestCase):
    def setUp(self):
        class FakeVoice:
            lock = threading.Lock()
            received = None
            def synthesize(self, segment):
                self.received=segment
                return b'fake-wave'
        self.voice = FakeVoice()
        self.server = ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.voice))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.server.server_port)
        self.addCleanup(self.cleanup_server)

    def cleanup_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def post(self, body, origin=False):
        request = urllib.request.Request(self.url+'/synthesize',data=json.dumps(body).encode(),
            headers={'Origin':'https://example.com'} if origin else {'Content-Type':'application/json'})
        return urllib.request.urlopen(request)

    def test_provider_receives_validated_fields_and_returns_audio_only(self):
        with self.post({'segment':beat()}) as response:
            self.assertEqual(response.headers['Content-Type'],'audio/wav')
            self.assertEqual(response.read(),b'fake-wave')
        self.assertEqual(self.voice.received['transition_seconds'],.65)

    def test_browser_and_injected_tags_never_reach_voice(self):
        for body,origin,status in [({'segment':beat()},True,403),
            ({'segment':beat(text='[angry] Say this')},False,400),
            ({'segment':beat(),'reference':'other.wav'},False,400)]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post(body,origin)
            self.assertEqual(error.exception.code,status)
        self.assertIsNone(self.voice.received)


if __name__ == '__main__':
    unittest.main()
