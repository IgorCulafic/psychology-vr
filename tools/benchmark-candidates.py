"""Run the existing dialogue suite against local GGUFs, sequentially, without a UI."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
from evaluation_suite import CASES
from model_evaluation import atomic_json, read_json, now, hardware_snapshot, process_token
from model_lab import Lab


def get(url, body=None, timeout=10):
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def weight_hash(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--languages', nargs='+', default=['bs', 'cnr'])
    parser.add_argument('--seeds', nargs='+', type=int, default=[42])
    parser.add_argument('--cases', nargs='+', default=['full'])
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifests = {m['key']: m for m in read_json(args.manifest)}
    unknown = set(args.models) - manifests.keys()
    if unknown:
        parser.error('Unknown models: ' + ', '.join(sorted(unknown)))
    ids = [c['id'] for c in CASES if args.cases == ['full'] or
           (args.cases == ['quick'] and c['quick']) or c['id'] in args.cases]
    if not ids:
        parser.error('No matching cases.')
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'batch.json').exists():
        parser.error('Use a fresh output directory; previous evidence is preserved.')
    endpoint = f'http://127.0.0.1:{args.port}'
    lab = Lab(endpoint, ROOT / 'services/.runtime/candidate-comparison/runs')
    if lab.active:
        parser.error('A candidate evaluation worker is already running.')
    batch = {'created_at': now(), 'models': [], 'status': 'running',
             'languages': args.languages, 'seeds': args.seeds, 'case_ids': ids,
             'hardware_before': hardware_snapshot(), 'note': 'Text only; no TTS or VR load. GPU memory is total device use, not per-process allocation.'}
    save = lambda: atomic_json(args.output / 'batch.json', batch)
    save()
    for key in args.models:
        model = manifests[key]
        record = {'key': key, 'manifest': model, 'status': 'preparing', 'started_at': now()}
        batch['models'].append(record)
        server = None
        run_id = None
        try:
            path = ROOT / model['path']
            if not path.is_file() or path.stat().st_size != model['bytes']:
                raise RuntimeError('Model download missing or incomplete: ' + str(path))
            checksum = weight_hash(path)
            record['sha256'] = checksum
            if model.get('sha256') and checksum != model['sha256']:
                raise RuntimeError('GGUF checksum mismatch.')
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', args.port)) == 0:
                    raise RuntimeError('Test port occupied; no existing server will be stopped.')
            command = [str(ROOT / model.get('runtime', '.tools/llama/llama-server.exe')),
                       '--model', str(path), '--alias', key, '--host', '127.0.0.1', '--port', str(args.port),
                       '--ctx-size', '4096', '--parallel', '1', '--n-gpu-layers', '99', '--batch-size', '256',
                       '--ubatch-size', '128', '--flash-attn', 'on', '--jinja', '--reasoning', 'off',
                       '--reasoning-budget', '0', '--chat-template-kwargs', '{"enable_thinking":false}',
                       '--spec-type', 'none']
            record['command'] = command
            record['gpu_samples'] = []
            with (args.output / f'{key}-server.log').open('wb') as log:
                server = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            record['server_pid'] = server.pid
            record['server_token'] = process_token(server.pid)
            save()
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Model server exited during loading; see server log.')
                try:
                    if get(endpoint + '/health')['status'] == 'ok':
                        break
                except Exception:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError('Model loading timed out.')
                time.sleep(1)
            # A small actual generation before the full patient schema/history workload.
            smoke = get(endpoint + '/v1/chat/completions', {
                'model': key, 'messages': [{'role': 'user', 'content': 'Odgovori samo brojem: koliko je 2 + 2?'}],
                'temperature': 0, 'max_tokens': 32, 'stream': False,
                'chat_template_kwargs': {'enable_thinking': False}}, timeout=90)
            record['smoke'] = smoke
            if not smoke.get('choices', [{}])[0].get('message', {}).get('content', '').strip():
                raise RuntimeError('No usable text in smoke response.')
            job = lab.start({'label': model['label'], 'languages': args.languages,
                             'seeds': args.seeds, 'case_ids': ids})
            run_id = job['id']
            record.update(status='running', run_id=run_id)
            save()
            print(json.dumps({'model': key, 'run_id': run_id, 'planned': job['planned_turns']}), flush=True)
            last = -1
            deadline = time.monotonic() + 2700
            while lab.process is not None and lab.process.poll() is None:
                result = read_json(lab.folder(run_id) / 'result.json')
                record['progress'] = result['progress']
                if result['progress']['done'] != last:
                    last = result['progress']['done']
                    print(json.dumps({'model': key, 'progress': result['progress'], 'current': result.get('current')}), flush=True)
                record['gpu_samples'].append({'at': now(), 'device': hardware_snapshot()['gpu_snapshot']})
                save()
                if time.monotonic() > deadline:
                    lab.cancel(run_id)
                    raise TimeoutError('45-minute model run limit reached; partial records retained.')
                time.sleep(5)
            lab.reconcile()
            result = lab.result(run_id)
            record.update(status=result['status'], summary=result['summary'], progress=result['progress'],
                          source_changed_during_run=result.get('source_changed_during_run'), error=result.get('error'))
            atomic_json(args.output / f'{key}-result.json', result)
        except KeyboardInterrupt:
            record.update(status='interrupted', error='Interrupted by operator.')
            raise
        except Exception as exc:
            record.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
            print(json.dumps({'model': key, 'error': record['error']}), flush=True)
        finally:
            if run_id and lab.process is not None and lab.process.poll() is None:
                lab.cancel(run_id)
                try:
                    lab.process.wait(timeout=100)
                except subprocess.TimeoutExpired:
                    lab.process.terminate()
                    lab.process.wait(timeout=10)
                lab.reconcile()
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
            record['finished_at'] = now()
            save()
    batch['status'] = 'completed' if all(m['status'] == 'completed' for m in batch['models']) else 'completed_with_failures'
    batch['finished_at'] = now()
    save()
    print(json.dumps({'status': batch['status'], 'output': str(args.output)}), flush=True)


if __name__ == '__main__':
    main()
