"""Best-effort system-wide resource samples; no dialogue, audio or credentials.

Runs outside inference and request threads. Missing NVIDIA tools/permissions are
recorded as unavailable, never as zero usage, and never stop a consultation.
"""
import csv
import ctypes
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def parse_gpus(raw):
    result = []
    for row in csv.reader(io.StringIO(raw)):
        if not row:
            continue
        if len(row) != 7:
            raise ValueError('Unexpected NVIDIA sample format')
        index, name, driver, total, used, utilization, temperature = [v.strip() for v in row]
        result.append(dict(index=index, name=name, driver=driver,
                           memory_total_mib=number(total), memory_used_mib=number(used),
                           utilization_percent=number(utilization), temperature_c=number(temperature)))
    return result


def system_memory():
    if os.name != 'nt':
        return None
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total_physical', 'available_physical', 'total_pagefile', 'available_pagefile',
             'total_virtual', 'available_virtual', 'available_extended_virtual')]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return dict(total_mib=round(status.total_physical / 1048576, 1),
                used_mib=round((status.total_physical - status.available_physical) / 1048576, 1),
                available_mib=round(status.available_physical / 1048576, 1))


class PerformanceLog:
    interval = 2.0

    def __init__(self, root, context):
        self.root = Path(root)
        self.context = context
        self.run_id = uuid.uuid4().hex
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None
        self.smi = shutil.which('nvidia-smi')

    def append(self, event, **fields):
        now = datetime.now(timezone.utc)
        directory = self.root / 'logs/performance' / now.strftime('%Y-%m-%d')
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / (self.run_id + '.jsonl')).open('a', encoding='utf-8') as out:
            out.write(json.dumps(dict(schema_version=1, timestamp=now.isoformat(),
                run_id=self.run_id, event=event, **fields), ensure_ascii=False, allow_nan=False) + '\n')
            out.flush()

    def sample(self):
        started = time.monotonic()
        gpus, gpu_error = [], None
        if self.smi:
            try:
                process = subprocess.run([self.smi,
                    '--query-gpu=index,name,driver_version,memory.total,memory.used,utilization.gpu,temperature.gpu',
                    '--format=csv,noheader,nounits'], capture_output=True, text=True,
                    timeout=1.5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if process.returncode:
                    gpu_error = 'nvidia_smi_exit_' + str(process.returncode)
                else:
                    gpus = parse_gpus(process.stdout)
                    if not gpus:
                        gpu_error = 'no_gpus_reported'
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                gpu_error = type(exc).__name__
        else:
            gpu_error = 'nvidia_smi_unavailable'
        self.append('sample', gpus=gpus, gpu_error=gpu_error,
                    system_ram=system_memory(), context=self.context(),
                    sample_duration_ms=round((time.monotonic() - started) * 1000))

    def start(self):
        self.thread = threading.Thread(target=self._run, name='resource-log', daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.append('monitor_started', interval_seconds=self.interval,
                scope='whole_system_all_applications', platform=platform.system(),
                os_version=platform.version(), logical_cpu_count=os.cpu_count(),
                context=self.context())
            while not self.stop_event.is_set():
                started = time.monotonic()
                self.sample()
                self.stop_event.wait(max(.1, self.interval - (time.monotonic() - started)))
            self.append('monitor_stopped')
        except Exception as exc:
            # Diagnostics must never become a dependency of speech or a live session.
            self.error = type(exc).__name__
            print('Resource logging stopped (' + self.error + '); conversation remains available.', flush=True)

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)


def bridge_context(bridge):
    with bridge.lock:
        config = bridge.config
        return dict(dialogue_model=config.get('dialogue_model'),
                    dialogue_provider=config.get('dialogue_provider'),
                    tts_provider=config.get('tts_provider'), higgs_quantization=config.get('higgs_quantization'),
                    stt_provider=config.get('stt_provider'), stt_device=config.get('stt_device'),
                    model_switching=bridge.models.switching,
                    reply_preparing=any(s.busy for s in bridge.sessions.values()),
                    playback_open=any(s.stream and not s.stream['closed'] for s in bridge.sessions.values()))
