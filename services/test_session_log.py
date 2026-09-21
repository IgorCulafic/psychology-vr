import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from alex_service import Bridge, ROOT, StaleTurn
from session_log import SessionLogError, read_records


class SessionLoggingTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime')
        self.addCleanup(self.folder.cleanup)
        config=json.loads((ROOT/'services/config.example.json').read_text())
        config.update(tts_provider='none',session_log_dir=self.folder.name,conversation_language='cnr')
        self.b=Bridge(config)
        self.key=self.b.new_session('ivan-work-exhaustion')['session_id']
        self.path=self.b.sessions[self.key].journal.path

    def test_written_immediately_with_unicode_cues_and_memory(self):
        self.assertEqual(read_records(self.path)[0]['event'],'session_started')
        reply=self.b.turn(self.key,'Čemu se nadate?')
        records=read_records(self.path)
        self.assertEqual([r['event'] for r in records],['session_started','turn_started','turn_completed'])
        self.assertEqual(records[1]['text'],'Čemu se nadate?')
        self.assertEqual(records[1]['request_id'],records[2]['request_id'])
        self.assertEqual(records[2]['response'],reply)
        self.assertNotIn('author_notes',self.path.read_text(encoding='utf-8'))
        self.assertIn('Student: Čemu se nadate?',self.path.with_suffix('.txt').read_text(encoding='utf-8'))

    def test_reset_rotates_file_without_erasing_previous_conversation(self):
        self.b.turn(self.key,'Before reset')
        self.b.invalidate(self.key,reset=True)
        new=self.b.sessions[self.key].journal.path
        self.assertNotEqual(new,self.path)
        self.b.turn(self.key,'After reset')
        old=read_records(self.path)
        self.assertEqual(old[-1]['reason'],'reset')
        self.assertNotIn('After reset',self.path.read_text(encoding='utf-8'))
        self.assertNotIn('Before reset',new.read_text(encoding='utf-8'))

    def test_replacement_preserves_old_log_and_marks_reason(self):
        self.b.turn(self.key,'First patient')
        other=self.b.new_session('nikola-bereavement',self.key)['session_id']
        self.assertEqual(read_records(self.path)[-1]['reason'],'replaced')
        self.assertNotEqual(self.b.sessions[other].journal.path,self.path)

    def test_failed_request_keeps_student_text_without_committing_reply(self):
        def fail(*args):raise RuntimeError('provider secret must not be logged')
        self.b.generate=fail
        with self.assertRaises(RuntimeError):self.b.turn(self.key,'Keep my question')
        records=read_records(self.path)
        self.assertEqual(records[-1]['event'],'turn_failed')
        self.assertEqual(records[-1]['error_type'],'RuntimeError')
        self.assertEqual(records[-2]['text'],'Keep my question')
        self.assertNotIn('provider secret',self.path.read_text(encoding='utf-8'))
        self.assertEqual(self.b.sessions[self.key].history,[])

    def test_cancelled_worker_stays_in_old_archive_after_reset(self):
        entered=threading.Event();release=threading.Event();errors=[]
        original=self.b.generate
        def slow(*args):entered.set();release.wait(3);return original(*args)
        self.b.generate=slow
        def work():
            try:self.b.turn(self.key,'Interrupted old question')
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=work);worker.start()
        self.assertTrue(entered.wait(2))
        self.b.invalidate(self.key,reset=True)
        new=self.b.sessions[self.key].journal.path
        release.set();worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0],StaleTurn)
        self.assertEqual(read_records(self.path)[-1]['event'],'turn_cancelled')
        self.assertEqual(len(read_records(new)),1)
        self.assertEqual(self.b.sessions[self.key].memory,[])

    def test_interrupt_after_reply_does_not_claim_it_was_heard(self):
        self.b.turn(self.key,'Hello')
        self.b.invalidate(self.key)
        records=read_records(self.path)
        self.assertEqual(records[-1]['event'],'interrupted')
        self.assertFalse(records[-1]['reply_in_progress'])
        self.assertIn('not confirmed',records[0]['playback_tracking'])

    def test_log_failure_stops_unrecorded_turn_and_leaves_session_usable(self):
        with patch.object(Path,'open',side_effect=PermissionError('blocked')):
            with self.assertRaises(SessionLogError):self.b.turn(self.key,'Not silently lost')
            with self.assertRaises(SessionLogError):self.b.new_session('nikola-bereavement',self.key)
            with self.assertRaises(SessionLogError):self.b.invalidate(self.key,reset=True)
        self.assertEqual(self.b.sessions[self.key].journal.path,self.path)
        self.assertFalse(self.b.sessions[self.key].busy)
        self.assertEqual(self.b.sessions[self.key].history,[])
        self.b.turn(self.key,'Can retry')

    def test_reader_recovers_complete_lines_after_truncated_crash_record(self):
        self.b.turn(self.key,'Saved')
        with self.path.open('ab') as handle:handle.write(b'{"incomplete":')
        self.assertEqual(len(read_records(self.path)),3)

    def test_journal_retains_dialogue_after_context_and_memory_trimming(self):
        for i in range(102):self.b.turn(self.key,f'Question number {i}')
        self.assertEqual(len(self.b.sessions[self.key].history),12)
        self.assertEqual(len(self.b.sessions[self.key].memory),96)
        starts=[r for r in read_records(self.path) if r['event']=='turn_started']
        self.assertEqual(len(starts),102)
        self.assertEqual(starts[0]['text'],'Question number 0')

if __name__=='__main__':unittest.main()
