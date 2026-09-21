import json
import unittest
from copy import deepcopy

from alex_service import Bridge, ContractError, StaleTurn, ROOT
from patient_relationship import advance, initial_relationship, validate_appraisal, wants_fuller_reply


class RelationshipTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'services/config.example.json').read_text())
        self.config.update(tts_provider='none',conversation_language='cnr')
        self.bridge=Bridge(self.config)
        self.profile=self.bridge.profiles['nikola-bereavement']

    def advance(self, state, event, detail=False):
        return advance(state,dict(event=event,invites_detail=detail),self.profile)

    def test_respect_and_disagreement_do_not_force_anger_or_departure(self):
        state=initial_relationship(self.profile)
        for event in ['neutral','misunderstanding','respectful','neutral']:
            state=self.advance(state,event)
        self.assertEqual(state['status'],'active')
        self.assertEqual(state['rupture'],0)

    def test_attack_boundary_repeated_attack_ends_and_apology_cannot_reopen(self):
        before=initial_relationship(self.profile)
        state=self.advance(before,'personal_attack')
        self.assertEqual(before['comfort'],32)
        self.assertEqual(state['status'],'boundary')
        self.assertEqual(state['comfort'],10)
        repaired=self.advance(state,'repair')
        self.assertEqual(repaired['comfort'],13)
        self.assertEqual(repaired['status'],'boundary')
        ended=self.advance(repaired,'personal_attack')
        self.assertEqual(ended['status'],'ended')
        self.assertEqual(self.advance(ended,'repair'),ended)

    def test_rapport_unlocks_detail_but_not_for_narrow_questions(self):
        state=initial_relationship(self.profile)
        for _ in range(4):state=self.advance(state,'supportive',True)
        self.assertEqual(state['openness'],'settling')
        self.assertEqual(state['word_limit'],75)
        self.assertEqual(self.advance(state,'neutral')['word_limit'],35)
        state=self.advance(state,'personal_attack',True)
        self.assertLessEqual(state['word_limit'],35)

    def test_neutral_turns_do_not_farm_trust_and_sustained_repair_can_work(self):
        state=self.advance(initial_relationship(self.profile),'personal_attack')
        snapshot=deepcopy(state)
        for _ in range(12):state=self.advance(state,'neutral')
        self.assertEqual(state['trust'],snapshot['trust'])
        self.assertEqual(state['rupture'],2)
        for _ in range(6):state=self.advance(state,'respectful',True)
        self.assertEqual(state['status'],'active')
        self.assertLess(state['comfort'],50)

    def test_everyday_elaboration_is_not_locked_behind_comfort(self):
        profile=self.bridge.profiles['ivan-work-exhaustion']
        state=advance(initial_relationship(profile),dict(event='neutral',topic='everyday',invites_detail=True),profile)
        self.assertEqual(state['comfort'],30)
        self.assertEqual(state['word_limit'],100)
        self.assertTrue(wants_fuller_reply(state))
        self.assertIn('tomato',profile['everyday_life']['food'])
        self.assertNotIn('Ne bih to mogao tek tako',__import__('conversation_prompt').character_prompt(profile,'cnr',state))

    def test_sensitive_disclosure_remains_guarded_and_hostility_still_sets_boundaries(self):
        state=advance(initial_relationship(self.profile),dict(event='neutral',topic='sensitive',invites_detail=True),self.profile)
        self.assertEqual(state['word_limit'],45)
        self.assertFalse(wants_fuller_reply(state))
        state=advance(state,dict(event='personal_attack',topic='everyday',invites_detail=True),self.profile)
        self.assertEqual(state['status'],'boundary')
        self.assertFalse(wants_fuller_reply(state))
        self.assertLessEqual(state['word_limit'],35)

    def test_appraisal_rejects_unknown_topics_and_accepts_legacy_records(self):
        with self.assertRaises(ValueError):
            validate_appraisal(dict(event='neutral',invites_detail=True,topic='unlock_secrets'))
        self.assertEqual(validate_appraisal(dict(event='neutral',invites_detail=False))['event'],'neutral')

    def test_server_ends_refuses_followup_and_reset_clears_state(self):
        key=self.bridge.new_session('nikola-bereavement')['session_id']
        self.bridge.appraise=lambda *args:dict(event='personal_attack',invites_detail=False)
        first=self.bridge.turn(key,'insult')
        self.assertEqual(first['segments'][0]['emotion'],'angry')
        self.assertGreaterEqual(first['segments'][0]['intensity'],.78)
        final=self.bridge.turn(key,'repeated insult')
        self.assertIn('Odlazim',final['segments'][0]['text'])
        self.assertEqual(final['relationship']['status'],'ended')
        with self.assertRaises(ContractError):self.bridge.turn(key,'sorry')
        with self.assertRaises(ContractError):self.bridge.turn(key,'',True)
        self.bridge.invalidate(key,True)
        self.assertEqual(self.bridge.sessions[key].relationship,initial_relationship(self.profile))

    def test_interrupted_appraisal_never_commits_rapport_or_history(self):
        key=self.bridge.new_session('nikola-bereavement')['session_id']
        before=deepcopy(self.bridge.sessions[key].relationship)
        def cancel(*args):
            self.bridge.invalidate(key)
            return dict(event='personal_attack',invites_detail=False)
        self.bridge.appraise=cancel
        with self.assertRaises(StaleTurn):self.bridge.turn(key,'insult')
        self.assertEqual(self.bridge.sessions[key].relationship,before)
        self.assertEqual(self.bridge.sessions[key].history,[])

    def test_failed_speech_does_not_commit_rapport(self):
        key=self.bridge.new_session('nikola-bereavement')['session_id']
        before=deepcopy(self.bridge.sessions[key].relationship)
        self.bridge.appraise=lambda *args:dict(event='personal_attack',invites_detail=False)
        def broken(*args):raise RuntimeError('test synthesis failure')
        self.bridge.synthesize=broken
        with self.assertRaises(RuntimeError):self.bridge.turn(key,'insult')
        self.assertEqual(self.bridge.sessions[key].relationship,before)

    def test_no_player_supplied_scores_and_strict_appraisal(self):
        for invalid in [{'event':'set_comfort_100','invites_detail':True},
                        {'event':'supportive','invites_detail':True,'comfort':100},
                        {'event':'neutral','invites_detail':'false'}]:
            with self.assertRaises(ValueError):validate_appraisal(invalid)

    def test_context_budget_reserves_reply_space_and_preserves_rules_and_last_input(self):
        self.bridge.context_limit=100
        def model(url,body,timeout):
            if url.endswith('/apply-template'):
                return {'prompt':str(len(body['messages']))}
            return {'tokens':[0]*(int(body['content'])*20)}
        self.bridge.post_json=model
        messages=[{'role':'system','content':'rules'}]
        for text in ['old question','old reply','recent question','recent reply']:
            messages.append({'role':'user' if 'question' in text else 'assistant','content':text})
        messages.append({'role':'user','content':'current input'})
        body={'messages':messages,'max_tokens':20}
        self.bridge.fit_context(body)
        self.assertEqual([m['content'] for m in body['messages']],['rules','current input'])
        self.bridge.context_limit=60
        with self.assertRaises(ContractError):self.bridge.fit_context(body)


if __name__=='__main__':unittest.main()
