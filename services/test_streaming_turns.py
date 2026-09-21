import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from alex_service import Bridge,ROOT,validate_reply
from session_log import read_records
from streaming_turns import sentence_segments
from performance_contract import refine_delivery,higgs_text,speech_text


def beat(text='First sentence. Second sentence.',**extra):
    return validate_reply({'segments':[dict(text=text,emotion='sad',intensity=.5,gesture='nod',voice_style='subdued',**extra)]})[0]


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime')
        self.addCleanup(self.folder.cleanup)
        config=json.loads((ROOT/'services/config.example.json').read_text())
        config.update(tts_provider='none',session_log_dir=self.folder.name)
        self.b=Bridge(config);self.b.runtime=Path(self.folder.name)
        self.b.generate=lambda *args:[beat()]
        self.key=self.b.new_session()['session_id']

    def wait(self,condition):
        deadline=time.monotonic()+3
        while not condition() and time.monotonic()<deadline:time.sleep(.005)
        self.assertTrue(condition())

    def start(self):
        turn=self.b.start_stream(self.key,'Tell me more')['turn_id']
        self.wait(lambda:self.b.poll_stream(self.key,turn)['done'])
        return turn

    def test_first_sentence_published_while_second_is_still_synthesizing(self):
        blocked=threading.Event();release=threading.Event();calls=[]
        def synth(segment,audio_id):
            calls.append(segment['text'])
            if len(calls)==2:blocked.set();release.wait(3)
        self.b.synthesize=synth
        turn=self.b.start_stream(self.key,'Tell me more')['turn_id']
        try:
            self.assertTrue(blocked.wait(2))
            state=self.b.poll_stream(self.key,turn)
            self.assertFalse(state['done']);self.assertEqual(len(state['segments']),1)
            self.assertEqual(self.b.sessions[self.key].history,[])
            self.b.acknowledge(self.key,turn,1)
            self.b.finish_stream(self.key,turn,1,reason='interrupted')
            self.assertEqual(self.b.sessions[self.key].memory[-1]['patient'],'First sentence.')
        finally:release.set()
        self.wait(lambda:self.b.poll_stream(self.key,turn)['done'])
        self.assertEqual(len(self.b.poll_stream(self.key,turn)['segments']),1)

    def test_completed_audio_only_is_committed_once(self):
        turn=self.start()
        self.assertEqual(self.b.sessions[self.key].history,[])
        self.b.finish_stream(self.key,turn,2)
        self.b.finish_stream(self.key,turn,2)
        self.assertEqual(len(self.b.sessions[self.key].history),2)
        self.assertEqual(self.b.sessions[self.key].memory[-1]['patient'],'First sentence. Second sentence.')
        self.assertFalse(self.b.sessions[self.key].busy)

    def test_partial_sentence_is_marked_not_guessed_or_memorized(self):
        turn=self.start();self.b.finish_stream(self.key,turn,1,.7,'interrupted')
        history=self.b.sessions[self.key].history[-1]['content']
        self.assertIn('unfinished sentence',history);self.assertNotIn('Second sentence',history)
        self.assertEqual(self.b.sessions[self.key].memory[-1]['patient'],'First sentence.')
        records=read_records(self.b.sessions[self.key].journal.path)
        self.assertTrue(records[-1]['partial_sentence_words_unknown'])
        self.assertEqual(records[-1]['confirmed_text'],'First sentence.')

    def test_out_of_order_and_invalid_acknowledgements(self):
        turn=self.start();self.b.acknowledge(self.key,turn,1,.8);self.b.acknowledge(self.key,turn,0)
        self.assertEqual(self.b.sessions[self.key].stream['completed_count'],1)
        for count,seconds in [(3,0),(True,0),(1,float('nan')),(1,-1)]:
            with self.assertRaises(ValueError):self.b.acknowledge(self.key,turn,count,seconds)
        self.b.acknowledge(self.key,turn,2)
        self.assertEqual(self.b.sessions[self.key].stream['partial_seconds'],0)
        with self.assertRaises(ValueError):self.b.acknowledge(self.key,'old-turn',1)

    def test_reset_preserves_ack_log_but_clears_memory_and_blocks_old_ack(self):
        turn=self.start();old=self.b.sessions[self.key].journal.path
        self.b.acknowledge(self.key,turn,1)
        self.b.invalidate(self.key,reset=True)
        self.assertEqual(self.b.sessions[self.key].memory,[])
        with self.assertRaises(ValueError):self.b.acknowledge(self.key,turn,2)
        self.assertTrue(any(r['event']=='playback_finished' for r in read_records(old)))

    def test_failure_after_first_sentence_preserves_played_prefix(self):
        def synth(segment,audio_id):
            if segment['text'].startswith('Second'):raise RuntimeError('speech failed')
        self.b.synthesize=synth;turn=self.start()
        self.assertTrue(self.b.poll_stream(self.key,turn)['error'])
        with self.assertRaises(ValueError):self.b.finish_stream(self.key,turn,1)
        self.b.finish_stream(self.key,turn,1,reason='interrupted')
        self.assertEqual(self.b.sessions[self.key].memory[-1]['patient'],'First sentence.')

    def test_reservation_blocks_duplicate_start_and_legacy_turn(self):
        turn=self.start()
        with self.assertRaises(ValueError):self.b.start_stream(self.key,'Another')
        with self.assertRaises(ValueError):self.b.turn(self.key,'Another')
        self.b.finish_stream(self.key,turn,0,reason='interrupted')
        self.assertEqual(self.b.sessions[self.key].memory[-1]['counsellor'],'Tell me more')
        self.assertEqual(self.b.sessions[self.key].memory[-1]['patient'],'')
        other=self.start();self.assertNotEqual(other,turn)

    def test_start_arriving_after_interrupt_cannot_restart_old_request(self):
        result=self.b.invalidate(self.key)
        with self.assertRaises(ValueError):self.b.start_stream(self.key,'Late old request',expected_generation=0)
        turn=self.b.start_stream(self.key,'Fresh request',expected_generation=result['generation'])['turn_id']
        self.wait(lambda:self.b.poll_stream(self.key,turn)['done'])
        finished=self.b.finish_stream(self.key,turn,2)
        self.assertGreater(finished['generation'],result['generation'])

    def test_split_preserves_unicode_abbreviations_and_single_gesture(self):
        parts=sentence_segments([beat('Dr. Marko je tu. Čekam ga. Zašto kasni?')])
        self.assertEqual([s['text'] for s in parts],['Dr. Marko je tu.','Čekam ga.','Zašto kasni?'])
        self.assertEqual(sum(s['gesture']=='nod' for s in parts),1)
        self.assertEqual(' '.join(s['text'] for s in parts),'Dr. Marko je tu. Čekam ga. Zašto kasni?')

    def test_delivery_suppresses_repeated_gestures_and_slows_settling(self):
        item=beat();item['emotion']='relieved'
        refined=refine_delivery([item],{'emotion':'angry','intensity':.8},['nod'])[0]
        self.assertEqual(refined['gesture'],'none');self.assertGreaterEqual(refined['transition_seconds'],.95)
        self.assertEqual(refined['text'],item['text']);self.assertEqual(refined['emotion'],'relieved')

    def test_pronunciation_alias_is_explicit_safe_and_does_not_change_transcript(self):
        text='Čujem Qwen, ne Qwenov glas.'
        self.assertEqual(speech_text(text,{'Qwen':'Kven'}),'Čujem Kven, ne Qwenov glas.')
        self.assertEqual(speech_text('rec\u0301i'),'reći')
        with self.assertRaises(ValueError):speech_text('Hello',{'Hello':'<|emotion:anger|>'})
        mild=dict(beat(),emotion='anxious',intensity=.4,voice_style='normal')
        self.assertNotIn('emotion:fear',higgs_text(mild))
        self.assertIn('emotion:fear',higgs_text(dict(mild,intensity=.8)))


if __name__=='__main__':unittest.main()
