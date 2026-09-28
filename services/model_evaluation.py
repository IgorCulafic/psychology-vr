"""Isolated, text-only evaluation worker; never changes production configuration."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time
import urllib.parse
import urllib.request

from evaluation_suite import CASES, LANGUAGES, VERSION, prompt_for

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'services/.runtime/model-lab'


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    # Windows readers/virus scanners can briefly hold the destination without
    # FILE_SHARE_DELETE. Keep the old complete JSON readable and retry the swap.
    for attempt in range(50):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(.1)


def read_json(path):
    # A replacement or scanner can briefly block even opening an intact result.
    for attempt in range(50):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8-sig'))
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(.1)


def local_endpoint(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost')
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ('', '/', '/v1/chat/completions')):
        raise ValueError('Use an HTTP model endpoint on localhost or 127.0.0.1.')
    return f'http://127.0.0.1:{parts.port or 80}'


def get_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def process_token(pid):
    """Read-only PID + creation-time identity, including after lab-server restart."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            return f'{pid}:{(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime}'
        finally:
            kernel.CloseHandle(handle)
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else f'{pid}:{fields[19]}'
    except (OSError, IndexError):
        return None


def model_snapshot(endpoint):
    base = local_endpoint(endpoint)
    models = get_json(base + '/v1/models')['data']
    if len(models) != 1:
        raise ValueError('Evaluation requires a single loaded llama.cpp model.')
    props = get_json(base + '/props')
    info = {'id': models[0]['id'], 'meta': models[0].get('meta', {}),
            'model_path': props.get('model_path'), 'build': props.get('build_info'),
            'generation_settings': props.get('default_generation_settings'),
            'chat_template_sha256': digest(props.get('chat_template', ''))}
    model_path = Path(info['model_path']) if info['model_path'] else None
    if model_path and model_path.is_file():
        stat = model_path.stat()
        info['weight_file'] = {'bytes': stat.st_size, 'modified_ns': stat.st_mtime_ns}
    info['identity'] = digest(info)
    return info


def source_snapshot():
    paths = list((ROOT / 'services').glob('*.py')) + list((ROOT / 'characters').glob('*/profile.json'))
    paths += [ROOT / 'characters/catalog.json', ROOT / 'unity/Assets/PsychologyVR/Resources/EmotionCatalog.json']
    return {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def hardware_snapshot():
    result = {'platform': platform.platform(), 'cpu': platform.processor(), 'logical_cpus': os.cpu_count(),
              'measurement': 'Text only. No TTS/Unity load is created by this runner. Other running apps may affect timings.'}
    try:
        proc = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,driver_version',
                               '--format=csv,noheader'], capture_output=True, text=True, timeout=5,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result['gpu_snapshot'] = proc.stdout.strip() if proc.returncode == 0 else 'Unavailable'
    except (OSError, subprocess.TimeoutExpired):
        result['gpu_snapshot'] = 'Unavailable'
    return result


def validate_selection(value):
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object.')
    allowed = {'label', 'languages', 'seeds', 'case_ids'}
    if set(value) - allowed:
        raise ValueError('Unknown run setting.')
    label = value.get('label', '')
    languages = value.get('languages', ['bs'])
    seeds = value.get('seeds', [42])
    ids = value.get('case_ids', [c['id'] for c in CASES if c['quick']])
    if not isinstance(label, str) or len(label) > 120:
        raise ValueError('Model label must be at most 120 characters.')
    label = label.strip()
    if not isinstance(languages, list) or not languages or any(not isinstance(x, str) or x not in LANGUAGES for x in languages):
        raise ValueError('Choose supported languages.')
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= 3 or any(type(x) is not int or not 0 <= x <= 2147483647 for x in seeds):
        raise ValueError('Use one to three integer seeds from 0 to 2147483647.')
    known = {c['id'] for c in CASES}
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or x not in known for x in ids):
        raise ValueError('Choose existing test scenarios.')
    if any(len(items) != len(set(items)) for items in (languages, seeds, ids)):
        raise ValueError('Duplicate languages, seeds or scenarios are not allowed.')
    return {'label': label, 'languages': languages, 'seeds': seeds, 'case_ids': ids}


def exact_check(reply, expected):
    # Formatting is deliberately part of these narrowly specified tasks.
    # Never use keyword presence as a proxy for semantic quality.
    return {'kind': 'exact_answer', 'expected': expected,
            'passed': isinstance(reply, str) and reply.strip() == expected}


def summarize(rows):
    groups = {}
    for row in rows:
        key = row['language'] + '/' + row['track']
        group = groups.setdefault(key, {'attempted': 0, 'completed': 0, 'errors': 0, 'skipped': 0,
                                       'exact_passed': 0, 'exact_total': 0, 'policy_departures': 0,
                                       'generation_retries': 0, 'truncated_calls': 0, 'times': []})
        if row['status'] == 'skipped':
            group['skipped'] += 1
            continue
        group['attempted'] += 1
        group['completed' if row['status'] == 'completed' else 'errors'] += 1
        if row['status'] == 'completed':
            group['times'].append(row['seconds'])
        group['policy_departures'] += int(row.get('source') == 'application_policy')
        calls = row.get('model_calls', [])
        group['generation_retries'] += max(0, sum(c.get('kind') == 'alex_reply' for c in calls) - 1)
        group['truncated_calls'] += sum(c.get('finish_reason') == 'length' for c in calls)
        for check in row.get('checks', []):
            if check['kind'] == 'exact_answer':
                group['exact_total'] += 1
                group['exact_passed'] += int(check['passed'])
    for group in groups.values():
        times = sorted(group.pop('times'))
        group['median_seconds'] = round(statistics.median(times), 3) if times else None
        group['p95_seconds'] = times[max(0, math.ceil(.95 * len(times)) - 1)] if times else None
    return groups


def language_guidance(language):
    dialect = {'bs': 'natural Bosnian, Latin script, ijekavian',
               'cnr': 'natural Montenegrin, Latin script, ijekavian',
               'sr': 'natural Serbian, Latin script, ekavian',
               'hr': 'natural Croatian, Latin script, ijekavian', 'en': 'natural English'}[language]
    return ('\nReply in ' + dialect + '. Preserve grammatical agreement and diacritics. '
            'Do not imitate the spelling of a different dialect in the question. '
            'Do not translate control enums or explicitly requested exact answer tokens.')


def install_trial_languages():
    """Patch only this dedicated worker process, never the running game/chat.

    Non-cnr trials use the same English-authored biography to avoid attributing
    an ijekavian source profile to native Serbian/Croatian localisation.
    """
    import alex_service
    original = alex_service.conversation_guidance
    def guidance(language, patient=False):
        if language == 'cnr':
            return original(language, patient)
        return original('en', patient) + language_guidance(language)
    alex_service.conversation_guidance = guidance


def evaluate_run(directory):
    import alex_service
    install_trial_languages()
    directory = Path(directory)
    job = read_json(directory / 'request.json')
    selection = validate_selection(job['selection'])
    suite = job['suite']
    result = {'id': job['id'], 'status': 'running', 'started_at': now(), 'metadata': job,
              'rows': [], 'summary': {}, 'progress': {'done': 0, 'total': job['planned_turns']}}
    def save():
        result['summary'] = summarize(result['rows'])
        atomic_json(directory / 'result.json', result)
    save()
    try:
        if source_snapshot() != job['source_files']:
            raise RuntimeError('Source changed after the run was queued. Start a new run.')
        first = True
        for seed in selection['seeds']:
            for language in selection['languages']:
                for scenario in suite:
                    history = []
                    config = {'dialogue_provider': 'llama.cpp', 'llm_url': job['endpoint'] + '/v1/chat/completions',
                              'llm_model': job['model']['id'], 'llm_timeout_seconds': 90,
                              'conversation_language': language, 'tts_provider': 'none',
                              'lip_sync_provider': 'none', 'stt_provider': 'disabled',
                              'session_source': 'model_evaluation', 'session_log_dir': str(directory / 'sessions')}
                    bridge = alex_service.Bridge(config)
                    key = bridge.new_session(scenario['character'])['session_id'] if scenario['character'] else None
                    calls = []
                    context_events = []
                    original_post = bridge.post_json
                    original_fit = bridge.fit_context
                    def post(url, body, timeout):
                        if not url.endswith('/chat/completions'):
                            return original_post(url, body, timeout)
                        # Explicit sampling controls make inherited server defaults visible and stable.
                        body = {**body, 'seed': seed, 'min_p': 0, 'repeat_penalty': 1.0,
                                'presence_penalty': 0, 'frequency_penalty': 0, 'cache_prompt': False}
                        record = {'kind': body.get('response_format', {}).get('json_schema', {}).get('name', 'reasoning'),
                                  'request': deepcopy(body)}
                        calls.append(record)
                        start = time.perf_counter()
                        try:
                            response = original_post(url, body, timeout)
                            choice = response['choices'][0]
                            record.update(message=choice.get('message'), finish_reason=choice.get('finish_reason'),
                                          usage=response.get('usage'), timings=response.get('timings'))
                            return response
                        except Exception as exc:
                            record['error'] = type(exc).__name__ + ': ' + str(exc)
                            raise
                        finally:
                            record['seconds'] = round(time.perf_counter() - start, 3)
                    def fit(body, recalled=None):
                        before = len(body['messages'])
                        selected = original_fit(body, recalled)
                        context_events.append({'messages_before': before, 'messages_after': len(body['messages']),
                                               'recalled_available': len(recalled or []), 'recalled_used': len(selected or [])})
                        return selected
                    bridge.post_json = post
                    bridge.fit_context = fit
                    skip_reason = None
                    for index, item in enumerate(scenario['turns']):
                        if (directory / 'cancel').exists():
                            result['status'] = 'cancelled'
                            return
                        if model_snapshot(job['endpoint'])['identity'] != job['model']['identity']:
                            raise RuntimeError('Loaded model or server settings changed. Run stopped to avoid mixed results.')
                        group_id = f"{scenario['id']}:{language}:{seed}"
                        row = {'id': f'{group_id}:{index}', 'group_id': group_id, 'case_id': scenario['id'],
                               'title': scenario['title'], 'track': scenario['track'], 'character': scenario['character'],
                               'language': language, 'seed': seed, 'turn': index + 1,
                               'input': prompt_for(item, language), 'expectation': item['expectation'],
                               'status': 'skipped' if skip_reason else 'running', 'checks': []}
                        result['current'] = {'case': scenario['title'], 'language': language, 'turn': index + 1, 'seed': seed}
                        save()
                        if skip_reason:
                            row['skip_reason'] = skip_reason
                        else:
                            calls.clear()
                            context_events.clear()
                            start = time.perf_counter()
                            row['first_request_in_run'] = first
                            first = False
                            try:
                                if key:
                                    response = bridge.turn(key, row['input'])
                                    row.update(reply=' '.join(s['text'] for s in response['segments']), response=response)
                                    row['source'] = 'model' if any(c['kind'] == 'alex_reply' for c in calls) else 'application_policy'
                                    if (response.get('relationship') or {}).get('status') == 'ended':
                                        skip_reason = 'Patient session ended; remaining prompts were not sent.'
                                else:
                                    if not history:
                                        history = [{'role': 'system', 'content': 'Answer the task accurately using the supplied facts. '
                                                    'Follow the requested output format. Do not reveal internal reasoning.' + language_guidance(language)}]
                                    history.append({'role': 'user', 'content': row['input']})
                                    body = {'model': config['llm_model'], 'messages': deepcopy(history), 'stream': False,
                                            'temperature': .7, 'top_p': .8, 'top_k': 20, 'max_tokens': 256,
                                            'chat_template_kwargs': {'enable_thinking': False}}
                                    bridge.fit_context(body)
                                    response = bridge.post_json(config['llm_url'], body, 90)
                                    row['reply'] = response['choices'][0]['message'].get('content') or ''
                                    row['source'] = 'model'
                                    history.append({'role': 'assistant', 'content': row['reply']})
                                row['status'] = 'completed'
                                row['words'] = len(row['reply'].split())
                                row['checks'].append({'kind': 'nonempty_reply', 'passed': bool(row['reply'].strip())})
                                if 'exact' in item:
                                    row['checks'].append(exact_check(row['reply'], item['exact']))
                            except Exception as exc:
                                row.update(status='error', error=type(exc).__name__ + ': ' + str(exc))
                                if 'exact' in item:
                                    row['checks'].append(exact_check(None, item['exact']))
                                skip_reason = 'Earlier turn failed; this conversation was not continued with missing history.'
                            finally:
                                row['seconds'] = round(time.perf_counter() - start, 3)
                                row['model_calls'] = deepcopy(calls)
                                row['context_events'] = deepcopy(context_events)
                        result['rows'].append(row)
                        result['progress']['done'] += 1
                        save()
                        print(json.dumps({'progress': result['progress'], 'case': scenario['id'], 'language': language,
                                          'turn': index + 1, 'status': row['status']}, ensure_ascii=True), flush=True)
        result['status'] = 'completed'
    except Exception as exc:
        result.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        result['finished_at'] = now()
        result.pop('current', None)
        result['source_changed_during_run'] = source_snapshot() != job['source_files']
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    evaluate_run(args.run_dir)
