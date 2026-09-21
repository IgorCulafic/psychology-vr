import copy
import json
from pathlib import Path
import unittest

from conversation_prompt import character_prompt, conversation_guidance


class CharacterLocalizationTests(unittest.TestCase):
    def test_localization_does_not_mutate_profile_or_override_rules(self):
        profile = dict(name='Morgan', facts=['Original'], rules=['Fixed rule'],
                       opening='Opening', openings={'cnr': 'Uvod'},
                       localizations={'cnr': dict(facts=['Prevod'], name='Alex', rules=['Wrong'])})
        before = copy.deepcopy(profile)
        selected = json.JSONDecoder().raw_decode(character_prompt(profile, 'cnr'))[0]
        self.assertEqual(selected['name'], 'Morgan')
        self.assertEqual(selected['rules'], ['Fixed rule'])
        self.assertEqual(selected['facts'], ['Prevod'])
        self.assertNotIn('opening', selected)
        self.assertNotIn('localizations', selected)
        self.assertEqual(json.loads(character_prompt(profile, 'en'))['facts'], ['Original'])
        self.assertEqual(profile, before)

    def test_alex_localization_preserves_biography(self):
        profile = json.loads((Path(__file__).resolve().parents[1] / 'characters/alex/profile.json').read_text(encoding='utf-8'))
        selected = json.JSONDecoder().raw_decode(character_prompt(profile, 'cnr'))[0]
        self.assertEqual(selected['age'], 35)
        self.assertEqual(len(selected['facts']), len(profile['facts']))
        self.assertIn('Niko iz porodice nije poginuo.', ' '.join(selected['facts']))
        self.assertEqual(selected['initial_state'], profile['initial_state'])

    def test_everyday_topic_foregrounds_interests_without_erasing_case_profile(self):
        profile=json.loads((Path(__file__).resolve().parents[1]/'characters/ivan/profile.json').read_text(encoding='utf-8'))
        before=copy.deepcopy(profile)
        prompt=character_prompt(profile,'cnr',dict(topic='everyday'))
        self.assertIn('bijelim lukom',prompt)
        self.assertNotIn('Nemirno spava',prompt)
        self.assertNotIn('"disclosure":',prompt)
        self.assertIn('Nemirno spava',character_prompt(profile,'cnr',dict(topic='difficulty')))
        self.assertEqual(profile,before)
        self.assertNotIn('Ne bih to mogao tek tako',prompt)
        self.assertNotIn('usually in 1-2 short sentences',conversation_guidance('cnr',patient=True))


if __name__ == '__main__':
    unittest.main()
