from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from performance_log import PerformanceLog, parse_gpus
from diagnostics_export import create_bundle, stats, summarize, timing_record


class PerformanceTests(unittest.TestCase):
    def test_gpu_load_and_memory_remain_distinct_and_unavailable_is_not_zero(self):
        gpus = parse_gpus('0, RTX 4090, 600.1, 24576, 16384, 50, 60\n1, Other, 600.1, 8192, [N/A], N/A, 0\n')
        self.assertEqual(gpus[0]['memory_used_mib'], 16384)
        self.assertEqual(gpus[0]['utilization_percent'], 50)
        self.assertIsNone(gpus[1]['memory_used_mib'])
        self.assertIsNone(gpus[1]['utilization_percent'])
        self.assertEqual(gpus[1]['temperature_c'], 0)

    def test_missing_gpu_tool_still_records_ram_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = PerformanceLog(directory, lambda: {'dialogue_model':'gemma'})
            monitor.smi = None
            with patch('performance_log.system_memory', return_value={'used_mib':12000}):
                monitor.sample()
            record = json.loads(next(Path(directory).rglob('*.jsonl')).read_text())
            self.assertEqual(record['gpus'], [])
            self.assertEqual(record['gpu_error'], 'nvidia_smi_unavailable')
            self.assertEqual(record['system_ram']['used_mib'], 12000)

    def test_gpu_timeout_is_a_missing_measurement_not_a_service_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = PerformanceLog(directory, lambda: {})
            monitor.smi = 'nvidia-smi'
            with patch('performance_log.subprocess.run', side_effect=subprocess.TimeoutExpired('nvidia-smi',1.5)):
                monitor.sample()
            record = json.loads(next(Path(directory).rglob('*.jsonl')).read_text())
            self.assertEqual(record['gpu_error'], 'TimeoutExpired')

    def test_disk_failure_stops_only_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = PerformanceLog(directory, lambda: {})
            with patch.object(monitor, 'append', side_effect=OSError()), patch('builtins.print'):
                monitor._run()
            self.assertEqual(monitor.error, 'OSError')

    def test_thread_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = PerformanceLog(directory, lambda: {})
            monitor.smi = None
            monitor.start()
            monitor.close()
            self.assertFalse(monitor.thread.is_alive())
            rows = [json.loads(line) for line in next(Path(directory).rglob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(rows[0]['event'], 'monitor_started')
            self.assertEqual(rows[-1]['event'], 'monitor_stopped')

    def test_timings_exclude_cached_openings_and_preserve_missing_values(self):
        timings = [dict(event='turn_started',request_id='a',turn_id='aa',opening=True),
                   dict(event='turn_started',request_id='b',turn_id='bb',opening=False),
                   dict(event='turn_completed',request_id='a',total_ms=10),
                   dict(event='turn_completed',request_id='b',total_ms=3000,generation_ms=1000),
                   dict(event='segment_ready',turn_id='aa',index=0,ready_ms=8),
                   dict(event='segment_ready',turn_id='bb',index=0,ready_ms=2800),
                   dict(event='segment_ready',turn_id='bb',index=1,ready_ms=2999)]
        summary = summarize([], timings)
        self.assertEqual(summary['replies']['conversation']['total_ms']['mean'], 3000)
        self.assertEqual(summary['replies']['conversation']['first_audio_ready_ms']['mean'], 2800)
        self.assertEqual(summary['replies']['opening']['first_audio_ready_ms']['mean'], 8)
        self.assertIsNone(summary['replies']['conversation']['speech_ms']['mean'])
        self.assertIsNone(stats([None, 'N/A', float('nan')])['mean'])

    def test_export_omits_transcripts_audio_secrets_and_recovers_complete_records(self):
        now = datetime(2026,10,4,18,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions = root/'logs/sessions/2026-10-04'
            sessions.mkdir(parents=True)
            base = dict(timestamp=now.isoformat(),session_id='test')
            rows = [dict(base,event='turn_started',request_id='r',opening=False,text='PRIVATE STUDENT'),
                    dict(base,event='turn_completed',request_id='r',response=dict(total_ms=3000,
                        segments=[dict(text='PRIVATE PATIENT',audio='PRIVATE AUDIO')],memory='PRIVATE MEMORY')),
                    dict(base,event='playback_finished',confirmed_text='PRIVATE PLAYBACK',reason='completed')]
            (sessions/'session.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"incomplete',encoding='utf-8')
            (sessions/'session.txt').write_text('PRIVATE TXT')
            resources = root/'logs/performance/2026-10-04'
            resources.mkdir(parents=True)
            resource = dict(base,event='sample',secret='PRIVATE KEY',context=dict(dialogue_model='gemma',secret='PRIVATE CONFIG'),
                            gpus=[dict(name='RTX 4090',memory_total_mib=24576,memory_used_mib=16384,utilization_percent=50)])
            (resources/'test.jsonl').write_text(json.dumps(resource)+'\n',encoding='utf-8')
            path, summary = create_bundle(root, now=now)
            self.assertEqual(summary['resource_samples'],1)
            self.assertEqual(summary['skipped_damaged_records'],1)
            with zipfile.ZipFile(path) as bundle:
                self.assertEqual(set(bundle.namelist()),{'SUMMARY.txt','summary.json','resources.jsonl','timings.jsonl'})
                for name in bundle.namelist():
                    self.assertNotIn('PRIVATE',bundle.read(name).decode('utf-8'))
            self.assertEqual(summary['gpus'][0]['memory_used_mib']['peak'],16384)
            self.assertEqual(summary['gpus'][0]['utilization_percent']['mean'],50)

    def test_old_sessions_and_unknown_event_payloads_are_excluded(self):
        self.assertIsNone(timing_record(dict(event='private_new_event',text='private')))
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory)/'logs/sessions/2020-01-01'
            old.mkdir(parents=True)
            (old/'old.jsonl').write_text('not even json')
            _, summary = create_bundle(directory)
            self.assertEqual(summary['skipped_damaged_records'],0)
            self.assertEqual(summary['resource_samples'],0)


if __name__ == '__main__':
    unittest.main()
