import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import zipfile

import alex_service
from alex_service import Bridge, ROOT, make_handler
from session_export import export_session
from session_log import read_records, student_filename


class SessionExportTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime')
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        config=json.loads((ROOT/'services/config.example.json').read_text())
        config.update(tts_provider='none',session_log_dir=str(self.root/'logs/sessions'))
        self.bridge=Bridge(config)
        self.key=self.bridge.new_session('ivan-work-exhaustion',student_name='  Ana Čukić  ')['session_id']
        self.journal=self.bridge.sessions[self.key].journal

    def archive(self,result):
        return self.root/result['directory']/result['filename']

    def test_unicode_name_content_and_safe_entry_names(self):
        self.bridge.turn(self.key,'Čemu se nadate?')
        result=export_session(self.root,self.bridge,self.key)
        self.assertEqual(set(result),{'ok','filename','directory'})
        self.assertTrue(result['ok']);self.assertEqual(result['directory'],'logs/exports')
        self.assertIn('Ana-Čukić',result['filename'])
        self.assertEqual(Path(result['filename']).name,result['filename'])
        with zipfile.ZipFile(self.archive(result)) as bundle:
            self.assertEqual(set(bundle.namelist()),{self.journal.path.name,self.journal.path.with_suffix('.txt').name})
            for name in bundle.namelist():
                self.assertEqual(name,Path(name).name)
                self.assertFalse(any(char in name for char in '/\\'))
            records=bundle.read(self.journal.path.name).decode('utf-8')
            readable=bundle.read(self.journal.path.with_suffix('.txt').name).decode('utf-8')
        self.assertEqual(json.loads(records.splitlines()[0])['student_name'],'Ana Čukić')
        self.assertIn('Student name: Ana Čukić',readable)
        self.assertIn('Čemu se nadate?',readable)
        self.assertEqual(records,self.journal.path.read_text(encoding='utf-8'))

    def test_repeat_exports_do_not_overwrite_logs_or_change_session(self):
        self.bridge.turn(self.key,'First question')
        before=self.journal.path.read_bytes()
        first=export_session(self.root,self.bridge,self.key)
        old_archive=self.archive(first).read_bytes()
        self.bridge.turn(self.key,'Second question')
        second=export_session(self.root,self.bridge,self.key)
        self.assertNotEqual(first['filename'],second['filename'])
        self.assertEqual(self.archive(first).read_bytes(),old_archive)
        self.assertTrue(self.journal.path.read_bytes().startswith(before))
        self.assertEqual(self.bridge.sessions[self.key].journal,self.journal)
        self.assertEqual(len(self.bridge.sessions[self.key].history),4)

    def test_maximum_length_unicode_name_fits_windows_paths_and_remains_complete_in_logs(self):
        # Deseret letters occupy two Windows UTF-16 units each. Their full
        # 80-character identity must survive while filesystem fragments stay short.
        name='\U00010400'*80
        key=self.bridge.new_session('ivan-work-exhaustion',self.key,student_name=name)['session_id']
        journal=self.bridge.sessions[key].journal
        self.assertTrue(journal.path.is_file())
        self.assertEqual(read_records(journal.path)[0]['student_name'],name)
        self.assertLessEqual(len(student_filename(name).encode('utf-16-le'))//2,48)
        result=export_session(self.root,self.bridge,key)
        archive=self.archive(result)
        self.assertTrue(archive.is_file())
        for path in (journal.path,journal.path.with_suffix('.txt'),archive):
            self.assertLessEqual(len(str(path).encode('utf-16-le'))//2,259)
            self.assertLessEqual(len(path.name.encode('utf-16-le'))//2,255)
        with zipfile.ZipFile(archive) as bundle:
            self.assertIn(name,bundle.read(journal.path.with_suffix('.txt').name).decode('utf-8'))

    def test_unknown_session_writes_nothing_and_unnamed_automation_has_fallback(self):
        with self.assertRaises(KeyError):export_session(self.root,self.bridge,'missing-session')
        self.assertFalse((self.root/'logs/exports').exists())
        key=self.bridge.new_session()['session_id']
        result=export_session(self.root,self.bridge,key)
        self.assertIn('student-',result['filename'])

    def test_snapshot_lock_keeps_readable_and_jsonl_pair_together(self):
        entered=threading.Event();release=threading.Event();appended=threading.Event()
        result=[];errors=[];original=Path.read_bytes
        def read(path):
            content=original(path)
            if path==self.journal.path:
                entered.set()
                if not release.wait(3):raise RuntimeError('Snapshot test timed out')
            return content
        def export():
            try:result.append(export_session(self.root,self.bridge,self.key))
            except Exception as error:errors.append(error)
        def append():
            self.journal.append('snapshot_test',marker='APPENDED_AFTER_SNAPSHOT');appended.set()
        writer=None
        with patch.object(Path,'read_bytes',read):
            worker=threading.Thread(target=export);worker.start()
            try:
                self.assertTrue(entered.wait(2))
                writer=threading.Thread(target=append);writer.start()
                self.assertFalse(appended.wait(.05))
            finally:release.set()
            worker.join(3)
            if writer is not None:writer.join(3)
        self.assertFalse(errors);self.assertFalse(worker.is_alive());self.assertIsNotNone(writer);self.assertFalse(writer.is_alive())
        self.assertTrue(appended.is_set())
        with zipfile.ZipFile(self.archive(result[0])) as bundle:
            for name in bundle.namelist():self.assertNotIn(b'APPENDED_AFTER_SNAPSHOT',bundle.read(name))
        self.assertIn('APPENDED_AFTER_SNAPSHOT',self.journal.path.read_text(encoding='utf-8'))

    def test_failed_export_cleans_temporary_zip_and_preserves_previous_files(self):
        first=export_session(self.root,self.bridge,self.key)
        archive_bytes=self.archive(first).read_bytes();journal_bytes=self.journal.path.read_bytes()
        with patch.object(zipfile.ZipFile,'writestr',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):export_session(self.root,self.bridge,self.key)
        self.assertEqual(self.archive(first).read_bytes(),archive_bytes)
        self.assertEqual(self.journal.path.read_bytes(),journal_bytes)
        self.assertEqual([p.name for p in (self.root/'logs/exports').iterdir()],[first['filename']])

    def test_export_http_response_contains_only_relative_download_metadata(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.bridge))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with patch.object(alex_service,'ROOT',self.root):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                connection.request('POST','/session/export',json.dumps({'session_id':self.key}),{'Content-Type':'application/json'})
                response=connection.getresponse();result=json.loads(response.read());connection.close()
            self.assertEqual(response.status,200)
            self.assertEqual(set(result),{'ok','filename','directory'})
            self.assertEqual(result['directory'],'logs/exports')
            self.assertTrue(self.archive(result).is_file())
            self.assertNotIn(str(self.root),json.dumps(result))
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main()
