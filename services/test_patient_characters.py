import json
from pathlib import Path
import unittest

from alex_service import Bridge, EMOTIONS
from conversation_prompt import character_prompt, PATIENT_GUIDANCE

ROOT=Path(__file__).resolve().parents[1]
NEW={'nikola-bereavement','stefan-fire-witness','ivan-work-exhaustion'}


class AdultPatientTests(unittest.TestCase):
    def setUp(self):
        config=json.loads((ROOT/'services/config.example.json').read_text())
        config.update(tts_provider='none',conversation_language='cnr')
        self.bridge=Bridge(config)

    def test_new_patients_are_adults_with_distinct_profiles_and_short_openings(self):
        catalog=self.bridge.public_catalog()['scenarios']
        self.assertTrue(NEW.issubset({entry['id'] for entry in catalog}))
        names=set()
        for entry in catalog:
            if entry['id'] not in NEW:continue
            profile=self.bridge.profiles[entry['id']]
            self.assertGreaterEqual(entry['age'],18)
            self.assertEqual(entry['age'],profile['age'])
            self.assertEqual(entry['character_name'],profile['name'])
            names.add(profile['name'])
            self.assertEqual(profile['interaction_style'],'patient_v1')
            self.assertIn(profile['initial_state']['emotion'],EMOTIONS)
            self.assertLessEqual(len(profile['openings']['cnr'].split()),30)
            self.assertEqual(set(profile['disclosure']),{'early','follow_up','sensitive'})
            self.assertTrue(profile['response_tendencies'])
        self.assertEqual(len(names),3)

    def test_teacher_notes_stay_out_of_model_and_public_catalog(self):
        for scenario in NEW:
            profile=self.bridge.profiles[scenario]
            profile['author_notes']['test_secret']='INSTRUCTOR_ONLY_SENTINEL'
            prompt=character_prompt(profile,'cnr')
            self.assertNotIn('INSTRUCTOR_ONLY_SENTINEL',prompt)
            self.assertNotIn('author_notes',prompt)
            self.assertIn(PATIENT_GUIDANCE,prompt)
            for other in NEW-{scenario}:
                self.assertNotIn(self.bridge.profiles[other]['name'],prompt)
        self.assertNotIn('INSTRUCTOR_ONLY_SENTINEL',json.dumps(self.bridge.public_catalog()))
        self.assertIn(PATIENT_GUIDANCE,character_prompt(self.bridge.profiles['alex-earthquake'],'cnr'))

    def test_each_selection_and_reset_uses_its_own_opening_and_emotion(self):
        key=self.bridge.new_session()['session_id']
        for scenario in sorted(NEW):
            key=self.bridge.new_session(scenario,key)['session_id']
            profile=self.bridge.profiles[scenario]
            opening=self.bridge.turn(key,'',True)['segments'][0]
            self.assertEqual(opening['text'],profile['openings']['cnr'])
            self.assertEqual(opening['emotion'],profile['initial_state']['emotion'])
            self.bridge.sessions[key].emotion='angry'
            self.bridge.invalidate(key,True)
            self.assertEqual(self.bridge.sessions[key].emotion,profile['initial_state']['emotion'])
            self.assertEqual(self.bridge.sessions[key].history,[])


if __name__=='__main__':unittest.main()
