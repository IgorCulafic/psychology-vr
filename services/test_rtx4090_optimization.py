import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from alex_service import Bridge, ROOT
from inference_runtime import server_arguments
from patient_relationship import initial_relationship

class HardwareOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'services/config.example.json').read_text())
        self.config.update(dialogue_provider='llama.cpp',tts_provider='none',llm_cache_slots=True,
                           llm_stable_prefix=True,llm_compact_delivery=True)

    def test_appraisal_and_dialogue_have_stable_prefix_and_distinct_slots(self):
        bridge=Bridge(self.config)
        bridge.fit_context=lambda body,**kwargs:[]
        calls=[]
        def request(url,body,timeout):
            calls.append(copy.deepcopy(body))
            content={'event':'neutral','topic':'other','invites_detail':False} if body['id_slot']==0 else {
                'segments':[dict(text='I still feel uneasy.',emotion='anxious',intensity=.4)]}
            return {'choices':[{'message':{'content':json.dumps(content)}}]}
        bridge.post_json=request
        profile=bridge.profiles['alex-earthquake']
        state=initial_relationship(profile)
        for trust in (15,60):
            state['trust']=trust
            bridge.appraise('How do you feel?',[],state,profile)
            bridge.generate('How do you feel?',[],False,dict(relationship=state,emotion='anxious',intensity=.4),profile)
        self.assertEqual([c['id_slot'] for c in calls],[0,1,0,1])
        self.assertEqual(calls[0]['messages'][0],calls[2]['messages'][0])
        self.assertEqual(calls[1]['messages'][0],calls[3]['messages'][0])
        self.assertNotEqual(calls[1]['messages'][-1],calls[3]['messages'][-1])
        self.assertTrue(all(c['cache_prompt'] for c in calls))

    def test_two_slots_each_keep_four_k_context_and_hardware_overrides(self):
        model=dict(model_path='gemma.gguf',gpu_layers=99)
        args=server_arguments(ROOT,dict(llm_cache_slots=True,llm_gpu_layers=32,
            llm_flash_attention=True,llm_kv_cache_type='q8_0'),model)
        for flag,value in [('--ctx-size','8192'),('--parallel','2'),('--n-gpu-layers','32'),('--cache-type-v','q8_0')]:
            self.assertEqual(args[args.index(flag)+1],value)

    def test_mtp_requires_matching_installed_draft_and_validates_limits(self):
        model=dict(model_path='gemma.gguf',gpu_layers=99)
        with self.assertRaisesRegex(ValueError,'matching MTP'):server_arguments(ROOT,dict(llm_mtp=True),model)
        with self.assertRaises(ValueError):server_arguments(ROOT,dict(llm_ubatch_size=512,llm_batch_size=256),model)
        with self.assertRaises(ValueError):server_arguments(ROOT,dict(llm_kv_cache_type='q8_0'),model)

    def test_context_budget_keeps_memory_out_of_stable_system_prefix(self):
        bridge=Bridge(self.config);bridge.context_limit=520
        def request(url,body,timeout):
            if url.endswith('/apply-template'):return {'prompt':' '.join(m['content'] for m in body['messages'])}
            return {'tokens':[0]*(len(body['content'])//4)}
        bridge.post_json=request
        body=dict(messages=[dict(role='system',content='FIXED FACTS'),dict(role='user',content='LATEST QUESTION')],max_tokens=100)
        recalled=[dict(turn=i,speaker='counsellor',quote=f'PRIORITY_{i} '+('detail '*30)) for i in range(8)]
        bridge.fit_context(body,recalled)
        self.assertEqual(body['messages'][0]['content'],'FIXED FACTS')
        self.assertIn('PRIORITY_0',body['messages'][-1]['content'])
        self.assertNotIn('PRIORITY_7',body['messages'][-1]['content'])

if __name__=='__main__':unittest.main()
