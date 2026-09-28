"""Local model comparison and human review, served on loopback only."""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

from evaluation_suite import CASES, LANGUAGES, RUBRIC, FLAGS, VERSION
from model_evaluation import (ROOT, RESULTS, atomic_json, read_json, local_endpoint,
                              model_snapshot, source_snapshot, hardware_snapshot,
                              digest, now, validate_selection, process_token)


class Lab:
    def __init__(self, endpoint, directory=RESULTS):
        self.endpoint = local_endpoint(endpoint)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.process = None
        self.active = None
        self.reconcile()

    def folder(self, key):
        if not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key):
            raise ValueError('Invalid run ID.')
        return self.directory / key

    def reconcile(self):
        if self.process is not None and self.process.poll() is not None:
            directory = self.folder(self.active)
            result = read_json(directory / 'result.json')
            if result['status'] in ('queued', 'running'):
                result.update(status='failed', finished_at=now(), error='Evaluation worker exited unexpectedly. Completed records were preserved.')
                atomic_json(directory / 'result.json', result)
            self.process = None
            self.active = None
        if self.process is None:
            self.active = None
            for path in self.directory.glob('*/result.json'):
                result = read_json(path)
                if result['status'] not in ('queued', 'running'):
                    continue
                receipt = path.parent / 'worker.json'
                worker = read_json(receipt) if receipt.is_file() else {}
                if worker.get('token') and process_token(worker['pid']) == worker['token']:
                    self.active = result['id']
                else:
                    result.update(status='failed', finished_at=now(), error='Worker was interrupted. Completed records were preserved; start a fresh run.')
                    atomic_json(path, result)

    def start(self, selection):
        selection = validate_selection(selection)
        with self.lock:
            self.reconcile()
            if self.active:
                raise ValueError('A run is already active. Stop it or wait for completion.')
            # Do not run two models concurrently against the same test queue.
            for path in self.directory.glob('*/result.json'):
                if read_json(path)['status'] in ('queued', 'running'):
                    raise ValueError('An earlier worker may still be running. Inspect its result/log before starting another run.')
            model = model_snapshot(self.endpoint)
            if not selection['label']:
                selection['label'] = Path(model.get('model_path') or model['id']).name
            suite = [deepcopy(c) for c in CASES if c['id'] in selection['case_ids']]
            sources = source_snapshot()
            key = uuid.uuid4().hex
            job = {'id': key, 'created_at': now(), 'selection': selection, 'endpoint': self.endpoint,
                   'model': model, 'hardware': hardware_snapshot(), 'suite_version': VERSION, 'suite': suite,
                   'source_files': sources, 'suite_sha256': digest(suite), 'source_sha256': digest(sources),
                   'planned_turns': sum(len(c['turns']) for c in suite) * len(selection['languages']) * len(selection['seeds']),
                   'protocol': {'patient': 'Production Bridge including appraisal, memory retrieval, rewrites and delivery refinement; text only.',
                                'reasoning': 'Direct multi-turn model requests without patient biography or disclosure limits.',
                                'language': 'cnr uses production localisation. Other languages use the same English-authored facts plus a trial output-language instruction. Regional inputs are shared ijekavian Latin script; native review required.',
                                'sampling': 'Dialogue/reasoning temperature .7, top_p .8, top_k 20; appraisal temperature 0; min_p 0, repeat_penalty 1; thinking disabled in requests; seeds recorded. Server defaults and raw requests retained.',
                                'timing': 'Wall time through the text pipeline, including appraisal/retries. First run request marked. Prompt caching requested off; this is not a cold-load or 4090/VR/audio benchmark.',
                                'scoring': 'Exact answers score narrow reasoning/format tasks only. Patient quality requires human review. Application-authored departure is labelled separately.'}}
            directory = self.folder(key)
            atomic_json(directory / 'request.json', job)
            atomic_json(directory / 'reviews.json', {})
            atomic_json(directory / 'result.json', {'id': key, 'status': 'queued', 'metadata': job,
                        'rows': [], 'summary': {}, 'progress': {'done': 0, 'total': job['planned_turns']}})
            try:
                with (directory / 'worker.log').open('wb') as log:
                    self.process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'services/model_evaluation.py'),
                                                     '--run-dir', str(directory)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.active = key
                atomic_json(directory / 'worker.json', {'pid': self.process.pid, 'token': process_token(self.process.pid)})
            except OSError as exc:
                result = read_json(directory / 'result.json')
                result.update(status='failed', error=str(exc), finished_at=now())
                atomic_json(directory / 'result.json', result)
                raise
            return {'id': key, 'planned_turns': job['planned_turns']}

    def cancel(self, key):
        with self.lock:
            self.reconcile()
            if key != self.active:
                raise ValueError('This run is not active.')
            (self.folder(key) / 'cancel').touch()
            return {'ok': True, 'message': 'Stop requested. The current model call/turn may finish before the worker stops.'}

    def runs(self):
        with self.lock:
            self.reconcile()
            rows = []
            for path in self.directory.glob('*/result.json'):
                result = read_json(path)
                meta = result['metadata']
                reviews = read_json(path.parent / 'reviews.json')
                rows.append({'id': result['id'], 'status': result['status'], 'label': meta['selection']['label'],
                             'created_at': meta['created_at'], 'selection': meta['selection'],
                             'progress': result['progress'], 'summary': result['summary'],
                             'reviewed_groups': sum(bool(v) for v in reviews.values()),
                             'current': result.get('current'), 'error': result.get('error'),
                             'suite_sha256': meta['suite_sha256'], 'source_sha256': meta['source_sha256']})
            return {'active': self.active, 'runs': sorted(rows, key=lambda r: r['created_at'], reverse=True)}

    def result(self, key):
        with self.lock:
            self.reconcile()
            directory = self.folder(key)
            result = read_json(directory / 'result.json')
            result['reviews'] = read_json(directory / 'reviews.json')
            return result

    def review(self, key, data):
        if not isinstance(data, dict):
            raise ValueError('Expected a review object.')
        group, reviewer = data.get('group_id'), data.get('reviewer', '')
        scores, notes, flags = data.get('scores', {}), data.get('notes', ''), data.get('flags', [])
        if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 60:
            raise ValueError('Use a reviewer name or initials (1–60 characters).')
        if not isinstance(notes, str) or len(notes) > 5000:
            raise ValueError('Review notes are limited to 5000 characters.')
        if not isinstance(scores, dict) or set(scores) - set(RUBRIC) or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
            raise ValueError('Scores must be 1–5. Leave unassessed dimensions blank.')
        if not isinstance(flags, list) or any(not isinstance(f, str) or f not in FLAGS for f in flags):
            raise ValueError('Unknown review flag.')
        with self.lock:
            result = self.result(key)
            group_rows = [r for r in result['rows'] if r['group_id'] == group]
            if not group_rows:
                raise ValueError('No recorded conversation matches this review.')
            if group_rows[0]['track'] == 'reasoning' and set(scores) & {'character', 'emotion'}:
                raise ValueError('Character and emotion scores do not apply to direct reasoning tasks.')
            path = self.folder(key) / 'reviews.json'
            reviews = read_json(path)
            # Keep multiple reviewers; updating the same review retains an audit history.
            entries = reviews.setdefault(group, {})
            identity = reviewer.strip()
            old = entries.get(identity)
            revisions = old.get('revisions', []) + [{k: v for k, v in old.items() if k != 'revisions'}] if old else []
            entries[identity] = {'reviewer': identity, 'scores': scores, 'notes': notes, 'flags': sorted(set(flags)),
                                 'updated_at': now(), 'turns_seen': len(group_rows), 'revisions': revisions}
            atomic_json(path, reviews)
            return {'ok': True}


def make_handler(lab):
    static = ROOT / 'services/model_lab_web'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            host = f'127.0.0.1:{self.server.server_port}'
            return (self.headers.get('Host') == host and self.headers.get('Origin', f'http://{host}') == f'http://{host}'
                    and self.headers.get('Sec-Fetch-Site') != 'cross-site')

        def reply(self, status, value, kind='application/json; charset=utf-8', download=False):
            data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="model-evaluation.json"')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.allowed():
                return self.reply(403, {'error': 'Use the local Model Lab address.'})
            try:
                if self.path == '/health':
                    return self.reply(200, {'service': 'psychology-model-lab'})
                if self.path == '/api/catalog':
                    return self.reply(200, {'suite_version': VERSION, 'cases': CASES, 'languages': LANGUAGES,
                                           'rubric': RUBRIC, 'flags': FLAGS, 'endpoint': lab.endpoint})
                if self.path == '/api/model':
                    return self.reply(200, model_snapshot(lab.endpoint))
                if self.path == '/api/runs':
                    return self.reply(200, lab.runs())
                if self.path.startswith('/api/run/') or self.path.startswith('/api/export/'):
                    return self.reply(200, lab.result(self.path.rsplit('/', 1)[1]), download=self.path.startswith('/api/export/'))
                files = {'/': ('index.html', 'text/html; charset=utf-8'),
                         '/lab.js': ('lab.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if self.path in files:
                    name, kind = files[self.path]
                    return self.reply(200, (static / name).read_bytes(), kind)
                return self.reply(404, {'error': 'Not found.'})
            except FileNotFoundError:
                return self.reply(404, {'error': 'Run not found.'})
            except (ValueError, KeyError) as exc:
                return self.reply(400, {'error': str(exc)})
            except Exception as exc:
                return self.reply(503, {'error': str(exc)})

        def do_POST(self):
            if not self.allowed():
                return self.reply(403, {'error': 'Use the local Model Lab address.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': 'Expected JSON.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 32768:
                    return self.reply(413, {'error': 'Request too large or empty.'})
                data = json.loads(self.rfile.read(size))
                if self.path == '/api/start':
                    return self.reply(200, lab.start(data))
                if self.path.startswith('/api/cancel/'):
                    return self.reply(200, lab.cancel(self.path.rsplit('/', 1)[1]))
                if self.path.startswith('/api/review/'):
                    return self.reply(200, lab.review(self.path.rsplit('/', 1)[1], data))
                return self.reply(404, {'error': 'Not found.'})
            except (ValueError, TypeError, KeyError) as exc:
                return self.reply(400, {'error': str(exc)})
            except Exception as exc:
                return self.reply(503, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8087')
    parser.add_argument('--port', type=int, default=8797)
    parser.add_argument('--results', type=Path, default=RESULTS)
    args = parser.parse_args()
    lab = Lab(args.endpoint, args.results)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(lab))
    print(f'Model Lab: http://127.0.0.1:{args.port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if lab.active:
            try:
                lab.cancel(lab.active)
            except ValueError:
                pass
        server.server_close()


if __name__ == '__main__':
    main()
