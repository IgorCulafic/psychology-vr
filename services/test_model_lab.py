import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from evaluation_suite import CASES, LANGUAGES, prompt_for
from model_evaluation import (atomic_json, read_json, local_endpoint, validate_selection,
                              exact_check, summarize, evaluate_run, source_snapshot, ROOT)
from model_lab import Lab, make_handler


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.lab = Lab('http://127.0.0.1:8087', self.directory)
        self.key = 'a' * 32

    def fixture(self, rows=None):
        folder = self.lab.folder(self.key)
        job = {'id': self.key, 'selection': {'label': 'Fixture', 'languages': ['bs'], 'seeds': [42], 'case_ids': ['schedule']},
               'created_at': '2026-01-01', 'suite_sha256': 'suite', 'source_sha256': 'source'}
        result = {'id': self.key, 'status': 'completed', 'metadata': job, 'rows': rows or [], 'summary': {},
                  'progress': {'done': len(rows or []), 'total': len(rows or [])}}
        atomic_json(folder / 'result.json', result)
        atomic_json(folder / 'reviews.json', {})
        return folder

    def test_suite_has_independent_scenarios_delayed_recall_and_all_languages(self):
        self.assertEqual(len(CASES), 16)
        self.assertEqual(sum(len(c['turns']) for c in CASES), 70)
        self.assertEqual(len({c['id'] for c in CASES}), len(CASES))
        self.assertGreaterEqual(len(next(c for c in CASES if c['id']=='delayed-correction')['turns']), 10)
        for case in CASES:
            for item in case['turns']:
                for language in LANGUAGES:
                    self.assertTrue(prompt_for(item, language))
                    self.assertLessEqual(len(prompt_for(item, language)), 2000)
                self.assertTrue(item['expectation'])

    def test_only_loopback_model_endpoints(self):
        self.assertEqual(local_endpoint('http://localhost:8088/v1/chat/completions'), 'http://127.0.0.1:8088')
        for url in ['https://example.com', 'http://127.0.0.1.evil:80', 'http://user@127.0.0.1:8087',
                    'http://127.0.0.1:8087?key=secret', 'file:///etc/passwd', 'http://192.168.1.1:8087']:
            with self.subTest(url=url), self.assertRaises(ValueError): local_endpoint(url)

    def test_source_snapshot_includes_actual_runtime_catalogs_and_profiles(self):
        snapshot = source_snapshot()
        self.assertIn('unity/Assets/PsychologyVR/Resources/EmotionCatalog.json', snapshot)
        catalog = read_json(ROOT / 'characters/catalog.json')
        for item in catalog['scenarios']:
            self.assertIn('characters/' + item['profile'], snapshot)

    def test_atomic_save_retries_transient_windows_reader_lock(self):
        target = self.directory / 'result.json'
        atomic_json(target, {'progress': 1})
        replace = os.replace
        attempts = []
        def locked_once(source, destination):
            attempts.append(destination)
            if len(attempts) == 1:
                self.assertEqual(read_json(target), {'progress': 1})
                raise PermissionError('reader holds destination')
            return replace(source, destination)
        with patch('model_evaluation.os.replace', side_effect=locked_once), patch('model_evaluation.time.sleep'):
            atomic_json(target, {'progress': 2})
        self.assertEqual(read_json(target), {'progress': 2})
        self.assertEqual(len(attempts), 2)

    def test_run_settings_reject_invalid_or_duplicate_values(self):
        for bad in [{'label': None}, {'seeds': [True]}, {'seeds': [42, 42]}, {'languages': ['bs', 'bs']},
                    {'languages': 'bs'}, {'case_ids': ['missing']}, {'seeds': []}, {'command': 'anything'}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate_selection(bad)
        self.assertEqual(validate_selection({})['languages'], ['bs'])

    def test_read_retries_transient_lock_but_does_not_mask_bad_json(self):
        with patch('model_evaluation.Path.read_text', side_effect=[PermissionError('busy'), '{"done":140}']) as read, patch('model_evaluation.time.sleep'):
            self.assertEqual(read_json(self.directory/'result.json'), {'done':140})
            self.assertEqual(read.call_count, 2)
        with patch('model_evaluation.Path.read_text', return_value='{broken') as read:
            with self.assertRaises(json.JSONDecodeError):
                read_json(self.directory/'result.json')
            self.assertEqual(read.call_count, 1)

    def test_exact_checks_do_not_reward_keyword_mentions(self):
        self.assertTrue(exact_check(' 14:45\n', '14:45')['passed'])
        for reply in ['Not 14:45, it is 15:25', '14:45 or 15:00', '', None]:
            self.assertFalse(exact_check(reply, '14:45')['passed'])

    def test_summary_separates_skips_errors_retries_and_policy(self):
        base = {'language': 'bs', 'track': 'patient', 'checks': [], 'seconds': 2}
        rows = [{**base, 'status':'completed', 'source':'application_policy'},
                {**base, 'status':'skipped'}, {**base, 'status':'error'},
                {**base, 'status':'completed', 'seconds':4, 'model_calls':[
                    {'kind':'alex_reply','finish_reason':'length'}, {'kind':'alex_reply','finish_reason':'stop'}]}]
        value = summarize(rows)['bs/patient']
        self.assertEqual((value['attempted'], value['completed'], value['skipped'], value['errors']), (3,2,1,1))
        self.assertEqual(value['median_seconds'], 3)
        self.assertEqual((value['generation_retries'], value['policy_departures'], value['truncated_calls']), (1,1,1))
        self.assertEqual(value['exact_total'], 0)

    def test_reviews_preserve_multiple_reviewers_and_revision_history(self):
        self.fixture([{'group_id':'schedule:bs:42','track':'reasoning'}])
        data = {'group_id':'schedule:bs:42','reviewer':'A','scores':{'language':2},'notes':'Turn 1 is ungrammatical.','flags':['meaning_lost']}
        self.lab.review(self.key, data)
        self.lab.review(self.key, {**data, 'reviewer':'B', 'scores':{'language':3}})
        self.lab.review(self.key, {**data, 'scores':{'language':1}})
        reviews = self.lab.result(self.key)['reviews']['schedule:bs:42']
        self.assertEqual(set(reviews), {'A','B'})
        self.assertEqual(reviews['A']['revisions'][0]['scores']['language'], 2)
        self.assertNotIn('emotion', reviews['A']['scores'])
        with self.assertRaises(ValueError): self.lab.review(self.key, {**data,'scores':{'emotion':5}})
        with self.assertRaises(ValueError): self.lab.review(self.key, {**data,'scores':{'language':True}})
        with self.assertRaises(ValueError): self.lab.review(self.key, {**data,'group_id':'unknown'})

    def test_export_path_cannot_escape_run_directory(self):
        for value in ['../secret', '..', '/tmp/file', 'g'*32, None]:
            with self.assertRaises(ValueError): self.lab.folder(value)

    def test_unexpected_worker_exit_preserves_partial_results(self):
        folder=self.fixture([{'group_id':'fixture','track':'reasoning'}])
        result=read_json(folder/'result.json');result['status']='running';atomic_json(folder/'result.json',result)
        class Dead:
            def poll(self): return 1
        self.lab.active=self.key;self.lab.process=Dead();self.lab.reconcile()
        result=self.lab.result(self.key)
        self.assertEqual(result['status'],'failed');self.assertEqual(len(result['rows']),1)
        self.assertIsNone(self.lab.active)

    def test_restart_recovers_live_worker_or_marks_dead_worker_failed(self):
        folder=self.fixture()
        result=read_json(folder/'result.json');result['status']='running';atomic_json(folder/'result.json',result)
        atomic_json(folder/'worker.json',{'pid':123,'token':'123:creation'})
        with patch('model_lab.process_token',return_value='123:creation'):
            restored=Lab(self.lab.endpoint,self.directory)
            self.assertEqual(restored.active,self.key)
            restored.cancel(self.key)
            self.assertTrue((folder/'cancel').exists())
        with patch('model_lab.process_token',return_value='123:different-creation'):
            restored=Lab(self.lab.endpoint,self.directory)
            self.assertIsNone(restored.active)
            self.assertEqual(restored.result(self.key)['status'],'failed')

    def test_cancel_is_cooperative_and_does_not_delete_results(self):
        folder=self.fixture()
        class Running:
            def poll(self): return None
        self.lab.active=self.key;self.lab.process=Running()
        self.lab.cancel(self.key)
        self.assertTrue((folder/'cancel').is_file())
        self.assertTrue((folder/'result.json').is_file())

    def test_http_rejects_cross_origin_and_serves_export(self):
        self.fixture()
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.lab))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        host=f'127.0.0.1:{server.server_port}'
        def request(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request(method,path,body=body,headers={'Host':host,**(headers or {})})
            r=conn.getresponse();data=r.read();status=r.status;conn.close();return status,data
        self.assertEqual(request('GET','/health')[0],200)
        self.assertEqual(request('GET','/api/catalog')[0],200)
        self.assertEqual(request('GET','/api/export/'+self.key)[0],200)
        self.assertEqual(request('GET','/api/run/../secret')[0],400)
        self.assertEqual(request('POST','/api/start','{}',{'Origin':'https://example.com','Content-Type':'application/json'})[0],403)
        self.assertEqual(request('POST','/api/start','{}',{'Content-Type':'text/plain'})[0],415)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)

    def run_fixture(self, case, bridge, cancelled=False):
        job={'id':'b'*32,'selection':{'label':'fixture','languages':['bs'],'seeds':[42],'case_ids':[case['id']]},
             'suite':[case],'endpoint':'http://127.0.0.1:8087','model':{'id':'fixture','identity':'same'},
             'planned_turns':len(case['turns']),'source_files':{}}
        atomic_json(self.directory/'request.json',job)
        if cancelled:(self.directory/'cancel').touch()
        with patch('model_evaluation.source_snapshot',return_value={}), patch('model_evaluation.model_snapshot',return_value={'identity':'same'}), \
             patch('model_evaluation.install_trial_languages'), patch('alex_service.Bridge',bridge):
            evaluate_run(self.directory)
        return read_json(self.directory/'result.json')

    def test_direct_multiturn_preserves_history_and_hides_expected_answers(self):
        class Fake:
            def __init__(self,config): pass
            def fit_context(self,body,recalled=None): return []
            @staticmethod
            def post_json(url,body,timeout):
                answer=['14:45','15:15','15:25'][(len(body['messages'])-2)//2]
                return {'choices':[{'message':{'content':answer},'finish_reason':'stop'}]}
        result=self.run_fixture(next(c for c in CASES if c['id']=='schedule'),Fake)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['summary']['bs/reasoning']['exact_passed'],3)
        self.assertEqual(len(result['rows'][-1]['model_calls'][0]['request']['messages']),6)
        for row in result['rows']:
            self.assertNotIn(row['expectation'],json.dumps(row['model_calls'][0]['request']))

    def test_failed_turn_does_not_continue_with_missing_history(self):
        class Fake:
            def __init__(self,config): pass
            def fit_context(self,body,recalled=None):return []
            @staticmethod
            def post_json(url,body,timeout):raise TimeoutError('fixture timeout')
        result=self.run_fixture(next(c for c in CASES if c['id']=='schedule'),Fake)
        self.assertEqual([r['status'] for r in result['rows']],['error','skipped','skipped'])
        self.assertEqual(result['summary']['bs/reasoning']['exact_passed'],0)

    def test_policy_departure_not_credited_to_model_and_later_turns_skipped(self):
        class Fake:
            def __init__(self,config):pass
            def fit_context(self,body,recalled=None):return []
            @staticmethod
            def post_json(url,body,timeout):raise AssertionError('No model call expected')
            def new_session(self,character):return {'session_id':'fixture'}
            def turn(self,key,text):return {'segments':[{'text':'I am leaving.'}],'relationship':{'status':'ended'}}
        result=self.run_fixture(next(c for c in CASES if c['id']=='abuse-boundary'),Fake)
        self.assertEqual(result['rows'][0]['source'],'application_policy')
        self.assertEqual(result['summary']['bs/patient']['policy_departures'],1)
        self.assertEqual(result['summary']['bs/patient']['skipped'],4)

    def test_cancelled_run_is_not_a_pass(self):
        class Fake:
            def __init__(self,config):pass
            def fit_context(self,body,recalled=None):pass
            def post_json(self,*args):raise AssertionError('Cancelled run must not generate')
        result=self.run_fixture(next(c for c in CASES if c['id']=='schedule'),Fake,True)
        self.assertEqual(result['status'],'cancelled');self.assertEqual(result['rows'],[])


if __name__=='__main__':unittest.main()
