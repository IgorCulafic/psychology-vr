import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from alex_service import Bridge, ContractError, StaleTurn, validate_reply, make_handler,validate_mouth_cues,EMOTIONS,EMOTION_CATALOG,SEGMENT_SCHEMA
from pathlib import Path

def segment(**overrides):
    value = {'text': 'I feel a little uneasy.', 'emotion': 'anxious', 'intensity': .6, 'gesture': 'look_down', 'voice_style': 'hesitant'}
    value.update(overrides)
    return {'segments': [value]}

def config():
    value = json.loads(Path(__file__).with_name('config.example.json').read_text())
    value['tts_provider'] = 'none'
    return value

class ContractTests(unittest.TestCase):
    def test_full_catalog_survives_validation_and_is_in_model_schema(self):
        self.assertGreaterEqual(len(EMOTIONS),20)
        self.assertEqual(len(EMOTIONS),len(set(EMOTIONS)))
        for emotion in EMOTIONS:
            with self.subTest(emotion=emotion):self.assertEqual(validate_reply(segment(emotion=emotion))[0]['emotion'],emotion)
        self.assertEqual(list(EMOTIONS),SEGMENT_SCHEMA['properties']['segments']['items']['properties']['emotion']['enum'])
        for preset in EMOTION_CATALOG['emotions']:
            self.assertTrue(preset['description'])
            for shape in preset['shapes']:self.assertTrue(0<=shape['weight']<=1)

    def test_common_emotion_aliases_preserve_meaning(self):
        for name,expected in [('fear','afraid'),('disgust','disgusted'),('anger','angry'),('sobbing','crying'),('depressed','despondent')]:
            self.assertEqual(validate_reply(segment(emotion=name))[0]['emotion'],expected)

    def test_mouth_timing_rejects_overlap_nonfinite_and_unknown_shapes(self):
        good=[{'start':0,'end':.1,'value':'X'},{'start':.1,'end':.3,'value':'D'}]
        self.assertEqual(validate_mouth_cues(good,1),good)
        for bad in [[None],[{'start':0,'end':float('nan'),'value':'A'}],
                    [{'start':0,'end':2,'value':'A'}],[{'start':1.02,'end':1.05,'value':'A'}],[{'start':0,'end':.1,'value':'think'}],
                    good+[{'start':.2,'end':.4,'value':'C'}]]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_mouth_cues(bad,1)

    def test_only_final_json_is_used(self):
        reply = '<think>This is not dialogue.</think>\n```json\n' + json.dumps(segment()) + '\n```'
        self.assertEqual(validate_reply(reply)[0]['text'], 'I feel a little uneasy.')

    def test_unclosed_reasoning_fails(self):
        with self.assertRaises(ContractError): validate_reply('<think>Not finished' + json.dumps(segment()))

    def test_embedded_control_syntax_fails(self):
        for text in ['Fine. *trigger:sad*', '<think>secret</think>', '[looks down] Hello', '{"secret":1}']:
            with self.subTest(text=text), self.assertRaises(ContractError): validate_reply(segment(text=text))

    def test_unknown_cues_fall_back_and_intensity_clamps(self):
        reply = validate_reply(segment(emotion='explode',gesture='leave_room',intensity=12))[0]
        self.assertEqual((reply['emotion'],reply['gesture'],reply['intensity']),('neutral','none',1))

    def test_nonfinite_and_boolean_intensity_rejected(self):
        for value in [float('nan'),float('inf'),True,'0.5']:
            with self.subTest(value=value), self.assertRaises(ContractError): validate_reply(segment(intensity=value))

    def test_empty_and_oversized_output_rejected(self):
        for value in [{'segments':[]},segment(text=''),segment(text='a'*701),{'segments':[None]}]:
            with self.subTest(value=value), self.assertRaises(ContractError): validate_reply(value)

class SessionTests(unittest.TestCase):
    def add_other_profile(self, bridge):
        bridge.profiles['test-situation']={'name':'Morgan','facts':['The test-only event is a lost job.'],
            'opening':'I am uncertain about my next step.','initial_state':{'emotion':'confused','intensity':.4}}

    def test_selected_profile_controls_opening_reset_and_model_context(self):
        cfg=config();cfg['dialogue_provider']='llama.cpp';bridge=Bridge(cfg);self.add_other_profile(bridge)
        key=bridge.new_session('test-situation')['session_id']
        reply=bridge.turn(key,'',True)
        self.assertEqual(reply['segments'][0]['text'],'I am uncertain about my next step.')
        self.assertEqual(reply['segments'][0]['emotion'],'confused')
        captured={}
        def post(url,body,timeout):
            captured.update(body);return {'choices':[{'message':{'content':json.dumps(segment())}}]}
        bridge.post_json=post;bridge.turn(key,'How are you?')
        prompt=captured['messages'][0]['content']
        self.assertIn('Morgan',prompt);self.assertNotIn('earthquake',prompt);self.assertNotIn('Alex',prompt)
        bridge.invalidate(key,True);self.assertEqual(bridge.sessions[key].emotion,'confused')
        self.assertEqual(bridge.sessions[key].history,[])

    def test_switch_during_generation_cannot_leak_old_reply(self):
        bridge=Bridge(config());self.add_other_profile(bridge);key=bridge.new_session()['session_id']
        started=threading.Event();release=threading.Event();failures=[]
        def slow(*args):started.set();release.wait(3);return segment()['segments']
        original=bridge.generate;bridge.generate=slow
        def work():
            try:bridge.turn(key,'Hello')
            except Exception as exc:failures.append(exc)
        worker=threading.Thread(target=work);worker.start();self.assertTrue(started.wait(2))
        switched=bridge.new_session('test-situation',key);release.set();worker.join(3)
        self.assertFalse(worker.is_alive());self.assertIsInstance(failures[0],StaleTurn)
        new_key=switched['session_id'];self.assertNotEqual(new_key,key);self.assertEqual(bridge.sessions[new_key].history,[])
        self.assertEqual(bridge.sessions[new_key].emotion,'confused');bridge.generate=original
        # A delayed stop or turn carrying the retired ID cannot affect the new profile.
        with self.assertRaises(KeyError):bridge.invalidate(key)
        with self.assertRaises(KeyError):bridge.turn(key,'This belongs to the old conversation')
        self.assertIn('uncertain',bridge.turn(new_key,'',True)['segments'][0]['text'])

    def test_invalid_selection_preserves_session_and_repeated_switches_reuse_slot(self):
        bridge=Bridge(config());key=bridge.new_session()['session_id'];bridge.turn(key,'Hello')
        with self.assertRaises(ContractError):bridge.new_session('../private',key)
        self.assertEqual(len(bridge.sessions[key].history),2)
        for _ in range(40):key=bridge.new_session('alex-earthquake',key)['session_id']
        self.assertEqual(len(bridge.sessions),1);self.assertEqual(bridge.sessions[key].history,[])

    def test_alignment_stays_out_of_character_history(self):
        bridge=Bridge(config());key=bridge.new_session()['session_id']
        bridge.synthesize=lambda *args:'/audio/example.wav'
        bridge.align_mouth=lambda *args:([{'start':0,'end':.1,'value':'A'}],'rhubarb')
        reply=bridge.turn(key,'Hello')
        self.assertEqual(reply['segments'][0]['lip_sync_source'],'rhubarb')
        history=bridge.sessions[key].history[-1]['content']
        self.assertNotIn('mouth_cues',history);self.assertNotIn('lip_sync_source',history)

    def test_missing_aligner_falls_back_without_losing_speech(self):
        settings=config();settings['lip_sync_provider']='rhubarb';settings['rhubarb_path']='.tools/missing-rhubarb.exe'
        bridge=Bridge(settings)
        self.assertEqual(bridge.align_mouth('does-not-exist','Hello'),([],'audio_envelope'))

    def test_reset_clears_memory_and_delivery(self):
        bridge=Bridge(config()); key=bridge.new_session()['session_id']
        bridge.turn(key,'Hello')
        self.assertEqual(len(bridge.sessions[key].history),2)
        bridge.invalidate(key,True)
        self.assertEqual(bridge.sessions[key].history,[])
        self.assertEqual(bridge.sessions[key].emotion,'anxious')

    def test_cancelled_generation_cannot_publish_or_change_history(self):
        bridge=Bridge(config()); key=bridge.new_session()['session_id']
        started=threading.Event(); release=threading.Event(); failures=[]
        def slow(*args):
            started.set(); release.wait(3); return segment()['segments']
        bridge.generate=slow
        def run():
            try: bridge.turn(key,'Hello')
            except Exception as exc: failures.append(exc)
        worker=threading.Thread(target=run); worker.start()
        self.assertTrue(started.wait(2)); bridge.invalidate(key,True); release.set(); worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(failures[0],StaleTurn)
        self.assertEqual(bridge.sessions[key].history,[])
        self.assertFalse(bridge.sessions[key].busy)

    def test_failure_releases_session(self):
        bridge=Bridge(config()); key=bridge.new_session()['session_id']
        def fail(*args): raise ContractError('Bad provider reply')
        bridge.generate=fail
        with self.assertRaises(ContractError): bridge.turn(key,'Hello')
        self.assertFalse(bridge.sessions[key].busy)
        self.assertEqual(bridge.sessions[key].history,[])

    def test_llm_request_disables_thinking_and_uses_schema(self):
        cfg=config(); cfg['dialogue_provider']='llama.cpp'; bridge=Bridge(cfg); captured={}
        def post(url,body,timeout):
            captured.update(body)
            return {'choices':[{'message':{'content':json.dumps(segment()),'reasoning_content':'never say this'}}]}
        bridge.post_json=post
        key=bridge.new_session()['session_id']; reply=bridge.turn(key,'Hello')
        self.assertFalse(captured['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(captured['response_format']['type'],'json_schema')
        self.assertNotIn('never say this',json.dumps(reply))

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Bridge(config())))
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.worker.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.worker.join()

    def post(self,path,value,headers=None):
        request=urllib.request.Request(self.url+path,data=json.dumps(value).encode(),headers=headers or {'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response: return json.load(response)

    def test_session_turn_reset(self):
        key=self.post('/session',{})['session_id']
        reply=self.post('/turn',{'session_id':key,'text':'Hello'})
        self.assertEqual(reply['dialogue_provider'],'scripted')
        self.assertEqual(len(reply['segments']),1)
        self.assertTrue(self.post('/reset',{'session_id':key})['ok'])

    def test_browser_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as result:
            self.post('/session',{}, {'Origin':'https://example.com'})
        self.assertEqual(result.exception.code,403)

    def test_catalog_and_explicit_selection(self):
        with urllib.request.urlopen(self.url+'/catalog') as response:catalog=json.load(response)
        entry=catalog['scenarios'][0];self.assertNotIn('profile',entry)
        selected=self.post('/session',{'scenario_id':entry['id']})
        self.assertEqual(selected['scenario_id'],entry['id']);self.assertEqual(selected['character_name'],entry['character_name'])
        with self.assertRaises(urllib.error.HTTPError) as result:self.post('/session',{'scenario_id':'missing'})
        self.assertEqual(result.exception.code,400)

    def test_audio_path_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as result:
            urllib.request.urlopen(self.url+'/audio/../config.example.json')
        self.assertEqual(result.exception.code,404)

if __name__=='__main__': unittest.main()
