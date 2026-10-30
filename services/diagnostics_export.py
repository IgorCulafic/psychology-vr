"""Export allowlisted resource data and timing events, never transcript text."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics
import uuid
import zipfile

from performance_log import number


def fields(record, names):
    return {k: record[k] for k in names if k in record}


def timing_record(record):
    event = record.get('event')
    selected = fields(record, ('schema_version', 'timestamp', 'archive_id', 'session_id',
                              'event', 'request_id', 'turn_id'))
    if event == 'session_started':
        selected.update(fields(record, ('scenario_id', 'character', 'language', 'source',
            'dialogue_provider', 'model', 'dialogue_model', 'tts_provider', 'performance_run_id')))
    elif event == 'turn_started':
        selected.update(fields(record, ('opening', 'playback_mode')))
    elif event == 'turn_completed':
        response = record.get('response', {})
        selected.update(fields(response, ('turn_id', 'generation_ms', 'speech_ms', 'alignment_ms', 'total_ms')))
    elif event == 'segment_ready':
        selected.update(fields(record, ('index', 'ready_ms')))
        selected.update(fields(record.get('segment', {}), ('audio_duration_seconds','speech_source',
            'speech_preparation_ms','alignment_preparation_ms','pause_before_seconds','hold_after_seconds')))
    elif event in ('turn_failed', 'turn_cancelled'):
        selected.update(fields(record, ('error_type',)))
    elif event in ('playback_progress', 'playback_finished'):
        selected.update(fields(record, ('completed_count', 'partial_seconds', 'reason')))
    elif event == 'dialogue_model_changed':
        selected.update(fields(record, ('model',)))
    else:
        return None
    return selected


def resource_record(record):
    selected = fields(record, ('schema_version', 'timestamp', 'run_id', 'event', 'interval_seconds',
        'scope', 'platform', 'os_version', 'logical_cpu_count', 'gpu_error', 'sample_duration_ms'))
    if 'context' in record:
        selected['context'] = fields(record['context'], ('dialogue_model', 'dialogue_provider',
            'tts_provider', 'higgs_quantization', 'stt_provider', 'stt_device',
            'model_switching', 'reply_preparing', 'playback_open'))
    selected['gpus'] = [fields(gpu, ('index', 'name', 'driver', 'memory_total_mib',
        'memory_used_mib', 'utilization_percent', 'temperature_c')) for gpu in record.get('gpus', [])]
    selected['system_ram'] = fields(record.get('system_ram') or {}, ('total_mib', 'used_mib', 'available_mib'))
    return selected


def load_since(directory, cutoff, transform, until=None):
    records, damaged = [], 0
    if not directory.exists():
        return records, damaged
    for path in sorted(directory.rglob('*.jsonl')):
        # All journals use UTC date directories. Ignore older files without reading them.
        if len(path.parent.name) == 10 and path.parent.name < cutoff.date().isoformat():
            continue
        with path.open('r', encoding='utf-8') as source:
            for line in source:
                try:
                    record = json.loads(line)
                    timestamp = datetime.fromisoformat(record['timestamp'])
                    if timestamp.tzinfo is None:
                        raise ValueError('Missing timestamp timezone')
                    if timestamp >= cutoff and (until is None or timestamp <= until):
                        selected = transform(record)
                        if selected:
                            records.append(selected)
                except (ValueError, KeyError, TypeError, AttributeError):
                    # Active/crashed logs can end in an incomplete JSON line.
                    damaged += 1
    records.sort(key=lambda r: r['timestamp'])
    return records, damaged


def stats(values):
    values = sorted(v for v in (number(v) for v in values) if v is not None)
    if not values:
        return dict(count=0, mean=None, median=None, p95=None, peak=None)
    return dict(count=len(values), mean=round(statistics.mean(values), 2),
                median=round(statistics.median(values), 2),
                p95=values[math.ceil(.95 * len(values)) - 1], peak=values[-1])


def summarize(resources, timings):
    samples = [r for r in resources if r['event'] == 'sample']
    gpus = {}
    for sample in samples:
        for gpu in sample['gpus']:
            key = str((gpu.get('index'), gpu.get('name'), gpu.get('memory_total_mib')))
            item = gpus.setdefault(key, dict(name=gpu.get('name'), index=gpu.get('index'),
                total_mib=gpu.get('memory_total_mib'), memory=[], load=[], active_memory=[]))
            item['memory'].append(gpu.get('memory_used_mib'))
            item['load'].append(gpu.get('utilization_percent'))
            context = sample.get('context', {})
            if context.get('reply_preparing') or context.get('playback_open'):
                item['active_memory'].append(gpu.get('memory_used_mib'))
    for gpu in gpus.values():
        gpu['memory_used_mib'] = stats(gpu.pop('memory'))
        gpu['utilization_percent'] = stats(gpu.pop('load'))
        gpu['during_reply_memory_mib'] = stats(gpu.pop('active_memory'))
    openings = {}
    for row in timings:
        if row['event'] == 'turn_started':
            for key in ('request_id', 'turn_id'):
                if row.get(key):
                    openings[row[key]] = row.get('opening')
    groups = {}
    for label, opening in [('conversation', False), ('opening', True)]:
        completed = [r for r in timings if r['event'] == 'turn_completed'
                     and openings.get(r.get('request_id')) is opening]
        ready = [r for r in timings if r['event'] == 'segment_ready' and r.get('index') == 0
                 and openings.get(r.get('turn_id')) is opening]
        groups[label] = {key: stats(r.get(key) for r in completed)
                        for key in ('generation_ms', 'speech_ms', 'alignment_ms', 'total_ms')}
        groups[label]['first_audio_ready_ms'] = stats(r.get('ready_ms') for r in ready)
    return dict(resource_samples=len(samples), gpus=list(gpus.values()),
        ram_used_mib=stats(r['system_ram'].get('used_mib') for r in samples),
        unavailable_gpu_samples=sum(bool(r.get('gpu_error')) for r in samples),
        replies=groups, failed_turns=sum(r['event']=='turn_failed' for r in timings),
        cancelled_turns=sum(r['event']=='turn_cancelled' for r in timings))


def create_bundle(root, days=7, now=None):
    if not 1 <= days <= 31:
        raise ValueError('Choose 1 to 31 days')
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    resources, bad_resources = load_since(root/'logs/performance', cutoff, resource_record, now)
    session_dir = root/'logs/sessions'
    config_path = root/'services/config.local.json'
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8-sig'))
        configured = Path(config.get('session_log_dir', 'logs/sessions'))
        session_dir = configured if configured.is_absolute() else root/configured
    timings, bad_timings = load_since(session_dir, cutoff, timing_record, now)
    summary = summarize(resources, timings)
    summary.update(exported_utc=now.isoformat(), from_utc=cutoff.isoformat(),
                   skipped_damaged_records=bad_resources+bad_timings)
    lines = ['Psychology VR diagnostics', f'UTC interval: {cutoff.isoformat()} to {now.isoformat()}',
        '', f'Resource samples: {summary["resource_samples"]}',
        f'Unavailable GPU samples: {summary["unavailable_gpu_samples"]}']
    for gpu in summary['gpus']:
        mem, load = gpu['memory_used_mib'], gpu['utilization_percent']
        lines += [f'GPU {gpu["index"]}: {gpu["name"]}',
                  f'  VRAM total / mean / sampled peak (MiB): {gpu["total_mib"]} / {mem["mean"]} / {mem["peak"]}',
                  f'  GPU utilization mean / sampled peak (%): {load["mean"]} / {load["peak"]}']
    lines += [f'System RAM sampled peak (MiB): {summary["ram_used_mib"]["peak"]}', '']
    for label, group in summary['replies'].items():
        lines.append(label.capitalize() + ' timing (milliseconds):')
        for key, value in group.items():
            lines.append(f'  {key}: n={value["count"]}, median={value["median"]}, p95={value["p95"]}, max={value["peak"]}')
    lines += ['', f'Failed turns: {summary["failed_turns"]}; cancelled: {summary["cancelled_turns"]}',
        f'Skipped incomplete/damaged records: {summary["skipped_damaged_records"]}', '',
        'Memory and utilization cover ALL applications, not just this game.',
        'Sampling interval is about 2 seconds; shorter peaks may be missed. Means are sample averages.',
        'First audio ready is server preparation time after accepted text, not time from microphone release.',
        'Playback progress is the client audio clock, not proof of what a participant heard.',
        'Opening timings (potentially cached) are separated from conversation timings.',
        'No headset FPS, dropped-frame or end-to-end STT measurement is included.',
        'None means unavailable, never zero. Older runs may have timings but no resource samples.',
        'No conversation text, recordings, credentials or raw service logs are included.',
        'Nothing was uploaded. Send this ZIP manually when requesting support.']
    output = root/'diagnostics'
    output.mkdir(parents=True, exist_ok=True)
    path = output/f'psychology-vr-diagnostics-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('SUMMARY.txt', '\n'.join(lines)+'\n')
        bundle.writestr('summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
        for name, records in [('resources.jsonl', resources), ('timings.jsonl', timings)]:
            bundle.writestr(name, ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records))
    return path, summary
