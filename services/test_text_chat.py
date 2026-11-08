import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from alex_service import Bridge, ROOT
from text_chat import make_handler


class TextChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / 'services/config.example.json').read_text())
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.config))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        merged = {'Content-Type': 'application/json'}
        merged.update(headers or {})
        connection.request('GET' if data is None else 'POST', path,
                           None if data is None else json.dumps(data), merged)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, raw

    def test_rejects_foreign_origin_host_form_and_path_traversal(self):
        self.assertEqual(self.request('/session', {}, {'Origin': 'https://example.org'})[0], 403)
        self.assertEqual(self.request('/catalog', headers={'Host': 'attacker.example'})[0], 403)
        self.assertEqual(self.request('/session', {}, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('/../config.local.json')[0], 404)

    def test_catalog_uses_the_selected_profile_conversation_language(self):
        previous=self.config.get('conversation_language')
        try:
            self.config['conversation_language']='en'
            status,raw=self.request('/catalog')
            self.assertEqual(status,200)
            self.assertEqual(json.loads(raw)['default_language'],'en')
            del self.config['conversation_language']
            self.assertEqual(json.loads(self.request('/catalog')[1])['default_language'],'cnr')
        finally:
            if previous is None:self.config.pop('conversation_language',None)
            else:self.config['conversation_language']=previous

    def test_each_patient_uses_own_opening_without_voice_and_retires_old_session(self):
        old = None
        for scenario in ['nikola-bereavement', 'stefan-fire-witness', 'ivan-work-exhaustion']:
            status, raw = self.request('/session', {'scenario_id': scenario, 'session_id': old})
            self.assertEqual(status, 200)
            current = json.loads(raw)['session_id']
            if old:
                self.assertEqual(self.request('/turn', {'session_id': old, 'text': 'Hello'})[0], 400)
            status, raw = self.request('/turn', {'session_id': current, 'opening': True})
            reply = json.loads(raw)
            self.assertEqual(status, 200)
            self.assertEqual(reply['tts_provider'], 'none')
            self.assertTrue(all(segment['audio_url'] is None for segment in reply['segments']))
            old = current
        self.assertEqual(self.config['tts_provider'], 'windows')  # Original config untouched.

    def test_language_and_real_turn_pipeline_are_forwarded(self):
        original = Bridge.generate
        seen = []
        def generate(bridge, text, history, opening, state, profile):
            seen.append((bridge.config['conversation_language'], text, profile['name']))
            return original(bridge, text, history, True, state, profile)
        with patch.object(Bridge, 'generate', generate):
            for language in ('cnr', 'en'):
                _, raw = self.request('/session', {'language': language, 'scenario_id': 'nikola-bereavement'})
                session = json.loads(raw)['session_id']
                self.assertEqual(self.request('/turn', {'language': language, 'session_id': session, 'text': 'How are you?'})[0], 200)
        self.assertEqual(seen, [('cnr', 'How are you?', 'Nikola'), ('en', 'How are you?', 'Nikola')])

    def test_student_name_is_normalized_and_forwarded_independently_of_patient(self):
        original=Bridge.new_session
        seen=[]
        def new_session(bridge,scenario_id=None,replace_session_id=None,student_name=''):
            seen.append(student_name)
            return original(bridge,scenario_id,replace_session_id,student_name)
        with patch.object(Bridge,'new_session',new_session):
            status,raw=self.request('/session',{'scenario_id':'nikola-bereavement','student_name':'  Ana Čulafić  '})
        self.assertEqual(status,200)
        self.assertEqual(seen,['  Ana Čulafić  '])
        result=json.loads(raw)
        self.assertEqual(result['student_name'],'Ana Čulafić')
        self.assertEqual(result['character_name'],'Nikola')

    def test_invalid_student_name_keeps_existing_conversation_usable(self):
        _,raw=self.request('/session',{'student_name':'Ana'})
        key=json.loads(raw)['session_id']
        for name in (None,123,'x'*81,'Ana\nMarko'):
            with self.subTest(name=name):
                status,_=self.request('/session',{'session_id':key,'student_name':name})
                self.assertEqual(status,400)
        self.assertEqual(self.request('/turn',{'session_id':key,'opening':True})[0],200)

    def test_interrupt_discards_pending_response(self):
        _, raw = self.request('/session', {'scenario_id': 'stefan-fire-witness'})
        session = json.loads(raw)['session_id']
        entered, finish = threading.Event(), threading.Event()
        original = Bridge.generate
        results = []
        def delayed(bridge, text, history, opening, state, profile):
            entered.set()
            finish.wait(5)
            return original(bridge, text, history, True, state, profile)
        with patch.object(Bridge, 'generate', delayed):
            worker = threading.Thread(target=lambda: results.append(self.request('/turn', {'session_id': session, 'text': 'Hello'})))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.request('/interrupt', {'session_id': session})[0], 200)
            finally:
                finish.set()
                worker.join(5)
        self.assertEqual(results[0][0], 409)


if __name__ == '__main__':
    unittest.main()
