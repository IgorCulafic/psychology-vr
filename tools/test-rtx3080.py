"""Isolated RTX 3080 measurements. Never writes config.local.json or downloads models."""
import argparse
import base64
from contextlib import contextmanager
import csv
import errno
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services'))
PORTS = (8087, 8765, 8766)
PROMPTS = ['Kako se osjećate sada?', 'Šta vam je danas bilo najteže?',
           'Možete li mi dati jedan konkretan primjer?', 'Možemo da usporimo. Šta bi vam sada pomoglo?']
SAMPLES = [('alex-earthquake', 'anxious', 'Još osjećam strah. Teško mi je da govorim o tome.'),
           ('ivan-work-exhaustion', 'angry', 'Stalno traže više od mene. Umoran sam od svega.'),
           ('stefan-fire-witness', 'sad', 'Ne znam kako da objasnim taj osjećaj. Sve mi se vraća.'),
           ('nikola-bereavement', 'sad', 'Nedostaje mi svaki dan. Ponekad samo želim da budem sam.')]
CREATE_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
GPU_FIELDS = ('index', 'name', 'memory.total', 'memory.used', 'utilization.gpu',
              'utilization.memory', 'temperature.gpu', 'power.draw',
              'clocks.current.sm', 'clocks.current.memory', 'pstate')


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def run_text(command, timeout=15):
    return subprocess.check_output(command, text=True, encoding='utf-8', errors='replace',
                                   timeout=timeout, creationflags=CREATE_FLAGS, stderr=subprocess.DEVNULL).strip()


def powershell(script):
    return json.loads(run_text(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], 25))


def gpu_sample():
    try:
        raw = run_text(['nvidia-smi', '--id=0', '--query-gpu=' + ','.join(GPU_FIELDS),
                        '--format=csv,noheader,nounits'], 5)
        values = next(csv.reader([raw], skipinitialspace=True))
        if len(values) != len(GPU_FIELDS):
            raise ValueError('Unexpected nvidia-smi format')
        result = {}
        for key, value in zip(GPU_FIELDS, values):
            try:
                result[key] = float(value)
            except ValueError:
                result[key] = value.strip()
        return dict(available=True, values=result)
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration) as exc:
        return dict(available=False, error=type(exc).__name__)


def windows_memory():
    if os.name != 'nt':
        return dict(available=False, reason='Windows counters required')
    script = r"""
    $ErrorActionPreference='Stop'
    $result=@{available=$false;scope='All Windows GPU adapters'}
    try {
      $cpu=Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average
      $os=Get-CimInstance Win32_OperatingSystem
      $result.cpu_percent=$cpu.Average
      $result.ram_free_gib=[math]::Round($os.FreePhysicalMemory/1MB,2)
    } catch { $result.system_metrics_unavailable=$true }
    try {
      $rows=@{}
      (Get-Counter '\GPU Process Memory(*)\Shared Usage','\GPU Process Memory(*)\Dedicated Usage').CounterSamples | ForEach-Object {
        if ($_.InstanceName -match '^pid_(\d+)_') {
          $key=$Matches[1]
          if (!$rows.ContainsKey($key)) {
            $p=Get-Process -Id ([int]$key) -ErrorAction SilentlyContinue
            $rows[$key]=@{pid=[int]$key;name=$p.ProcessName;shared_mib=0;dedicated_mib=0}
          }
          $field=if ($_.Path -match '\\shared usage$') {'shared_mib'} else {'dedicated_mib'}
          $rows[$key][$field]+=[math]::Round($_.CookedValue/1MB,1)
        }
      }
      $result.available=$true
      $result.processes=@($rows.Values | Where-Object {$_.shared_mib -gt 1 -or $_.dedicated_mib -gt 1})
    } catch { $result.reason='GPU performance counters unavailable' }
    $result | ConvertTo-Json -Depth 5 -Compress
    """
    try:
        return powershell(script)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return dict(available=False, reason=type(exc).__name__)


def hardware():
    result = dict(os=platform.platform(), python=sys.version.split()[0], gpu=gpu_sample())
    try:
        result['windows'] = powershell(r"""
        $cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
        $os=Get-CimInstance Win32_OperatingSystem
        @{cpu=@($cpu);ram_total_gib=[math]::Round($os.TotalVisibleMemorySize/1MB,2);
          ram_free_gib=[math]::Round($os.FreePhysicalMemory/1MB,2);
          game_running=[bool](Get-Process -Name AlexPrototype -ErrorAction SilentlyContinue)} | ConvertTo-Json -Depth 4 -Compress
        """)
        result['driver'] = run_text(['nvidia-smi', '--id=0', '--query-gpu=driver_version', '--format=csv,noheader'])
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        result['windows_error'] = type(exc).__name__
    result['versions'] = {}
    for package in ('torch', 'transformers', 'faster-whisper', 'ctranslate2', 'bitsandbytes'):
        try:
            result['versions'][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result['versions'][package] = None
    result['free_disk_gib'] = round(shutil.disk_usage(ROOT).free / 1024**3, 2)
    catalog = read(ROOT / 'services/dialogue-models.json')['models']
    result['installed_dialogue_models'] = [dict(id=m['id'], installed=(ROOT / m['model_path']).is_file()) for m in catalog]
    return result


def occupied_ports():
    occupied = []
    for port in PORTS:
        with socket.socket() as sock:
            # A short connect timeout can return WSAEWOULDBLOCK even for a free
            # Windows port. Exclusive bind checks availability without contacting
            # or sending requests to another application's listener.
            if os.name == 'nt':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE or getattr(exc, 'winerror', None) == 10048:
                    occupied.append(port)
                else:
                    raise RuntimeError(f'Cannot verify loopback port {port} ({type(exc).__name__}); no model was started') from exc
    return occupied


def require_idle():
    ports = occupied_ports()
    if ports:
        raise RuntimeError('Existing service on port(s) ' + ', '.join(map(str, ports)) +
                           '. Close the application and use Stop Services.cmd, then rerun. No existing process was stopped.')


def stop_owned(process):
    """Only terminate the still-running Popen object created by this test, including venv children."""
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, creationflags=CREATE_FLAGS)
    else:
        process.terminate()
    try:
        process.wait(15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(10)


@contextmanager
def owned(command, log):
    with Path(log).open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=CREATE_FLAGS)
        try:
            yield process
        finally:
            stop_owned(process)


def wait_health(process, port, timeout=240):
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        if process.poll() is not None:
            raise RuntimeError('Model worker exited; inspect its server log')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                data = json.load(response)
                healthy = (data.get('status') == 'ok') if port == 8087 else (
                    data.get('ok') is True and data.get('provider') == 'higgs')
                if healthy:
                    return round(time.perf_counter() - started, 3)
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    raise TimeoutError('Model startup exceeded limit; inspect server log')


class Telemetry:
    def __init__(self, output):
        self.output, self.stop_event = Path(output), threading.Event()
        self.phase = 'preflight'
        self.thread = threading.Thread(target=self.collect, daemon=True)

    def collect(self):
        last_memory = -100
        with (self.output / 'gpu-telemetry.jsonl').open('w', encoding='utf-8') as stream:
            while not self.stop_event.is_set():
                now = time.monotonic()
                row = dict(utc=datetime.now(timezone.utc).isoformat(), phase=self.phase, gpu=gpu_sample())
                if now - last_memory >= 10:
                    row['windows_gpu_memory'] = windows_memory()
                    last_memory = now
                stream.write(json.dumps(row) + '\n')
                stream.flush()
                self.stop_event.wait(2)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stop_event.set()
        self.thread.join(35)


def summary(values):
    if not values:
        return dict(count=0, median_seconds=None, p90_seconds=None, max_seconds=None)
    ordered = sorted(values)
    position = (len(ordered) - 1) * .9
    low = int(position)
    p90 = ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)
    return dict(count=len(values), median_seconds=round(statistics.median(values), 3),
                p90_seconds=round(p90, 3), max_seconds=round(max(values), 3))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dialogue_worker(config, output, turns):
    from alex_service import Bridge
    bridge = Bridge(config)
    original = bridge.post_json
    def seeded(url, body, timeout):
        if url.endswith('/chat/completions'):
            body['seed'] = 42
        return original(url, body, timeout)
    bridge.post_json = seeded
    key = bridge.new_session('alex-earthquake')['session_id']
    report = dict(samples=[], includes_speech=False, includes_stt=False, includes_playback=False)
    for index in range(turns):
        bridge.last_inference_metrics = []
        started = time.perf_counter()
        reply = bridge.turn(key, PROMPTS[index % len(PROMPTS)])
        report['samples'].append(dict(index=index, first_after_model_load=index == 0,
            seconds=round(time.perf_counter() - started, 3),
            spoken_words=sum(len(s['text'].split()) for s in reply['segments']),
            segments=[{k:s[k] for k in ('text', 'emotion')} for s in reply['segments']],
            inference=bridge.last_inference_metrics[:]))
        save(output / 'report.json', report)
        print(f'Dialogue sample {index+1}/{turns} completed', flush=True)
    values = [row['seconds'] for row in report['samples']]
    report.update(summary(values), cold_seconds=values[0], warm=summary(values[1:]))
    return report


def voice_worker(config, output, repeats):
    from alex_service import validate_reply
    from higgs_service import HiggsVoice
    from speech_reuse import wav_duration
    started = time.perf_counter()
    voice = HiggsVoice(config)
    report = dict(load_seconds=round(time.perf_counter() - started, 3), samples=[],
                  precision=config['higgs_quantization'], fast_decode=config['higgs_fast_decode'],
                  sentence_streaming=config['higgs_sentence_streaming'], includes_llm=False,
                  includes_stt=False, includes_playback=False, native_voice_quality_verified=False)
    (output / 'wavs').mkdir(exist_ok=True)
    for repeat in range(repeats):
        for scenario, emotion, text in SAMPLES:
            segment = validate_reply({'segments':[dict(text=text, emotion=emotion, intensity=.6)]})[0]
            voice.torch.cuda.synchronize()
            voice.torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            audio = voice.synthesize(segment, scenario)
            voice.torch.cuda.synchronize()
            seconds = time.perf_counter() - started
            duration = wav_duration(audio)
            filename = f'{scenario}-{repeat}.wav'
            (output / 'wavs' / filename).write_bytes(audio)
            report['samples'].append(dict(scenario=scenario, emotion=emotion, text=text, repeat=repeat,
                first_reference_use=repeat == 0, seconds=round(seconds, 3), audio_seconds=duration,
                real_time_factor=round(seconds / duration, 3), wav='wavs/' + filename,
                sha256=hashlib.sha256(audio).hexdigest(),
                peak_allocated_mib=round(voice.torch.cuda.max_memory_allocated()/1024**2),
                peak_reserved_mib=round(voice.torch.cuda.max_memory_reserved()/1024**2)))
            save(output / 'report.json', report)
    report.update(summary([r['seconds'] for r in report['samples']]),
                  warm=summary([r['seconds'] for r in report['samples'] if r['repeat'] > 0]))
    return report


def default_audio():
    manifest = read(ROOT / 'voices/recorded/manifest.json')
    clip = next(c for c in manifest['clips'] if c['scenario_id'] == 'alex-earthquake' and c['approved'])
    path = ROOT / clip['audio']
    if digest(path) != clip['sha256']:
        raise ValueError('Default STT fixture is missing or its checksum differs')
    return path, clip['text']


def stt_worker(config, output, audio, repeats):
    from alex_service import Bridge
    if audio:
        path, expected = Path(audio), None
    else:
        path, expected = default_audio()
    encoded = base64.b64encode(path.read_bytes()).decode()
    bridge = Bridge(config)
    started = time.perf_counter()
    bridge.load_stt()
    report = dict(load_seconds=round(time.perf_counter() - started, 3), samples=[],
        language='sr (proxy for Montenegrin)', script='Latin', device='cpu', compute_type='int8',
        model=config['stt_model'], expected=expected, includes_microphone=False,
        accuracy_review_required=True)
    bridge.transcribe(encoded)  # Excluded kernel warm-up, same WAV validation as the app.
    for repeat in range(repeats):
        for beam in ((5, 1) if repeat % 2 == 0 else (1, 5)):
            bridge.config['stt_beam_size'] = beam
            started = time.perf_counter()
            transcript = bridge.transcribe(encoded)['text']
            report['samples'].append(dict(repeat=repeat, beam=beam, transcript=transcript,
                                         seconds=round(time.perf_counter() - started, 3)))
            save(output / 'report.json', report)
    report['by_beam'] = {str(b):summary([r['seconds'] for r in report['samples'] if r['beam']==b]) for b in (1, 5)}
    return report


def worker(args):
    output = args.output
    config = read(args.config)
    output.mkdir(parents=True, exist_ok=True)
    if args.stage == 'dialogue':
        result = dialogue_worker(config, output, args.turns)
    elif args.stage == 'voice':
        result = voice_worker(config, output, args.repeats)
    elif args.stage == 'stt':
        result = stt_worker(config, output, args.audio, args.repeats)
    elif args.stage == 'voice-ab':
        tool = ROOT / 'tools/benchmark-higgs.py'
        # Run in this worker, so one owned process tree contains all speech memory.
        sys.argv = [str(tool), '--config', str(args.config), '--output', str(output), '--repeats', str(args.repeats)]
        load_module('voice_ab_3080', tool).main()
        return
    else:
        tool = load_module('response_3080', ROOT / 'tools/benchmark-response.py')
        tool.check_workers(config)
        audio = args.audio or default_audio()[0]
        result = tool.benchmark(config, output, args.turns, audio, 14)
        if not result['completed']:
            raise RuntimeError('Combined benchmark incomplete; inspect report.json')
    save(output / 'report.json', result)


def stage_config(base, stage, case, vram):
    config = dict(base)
    config.update(stt_warmup=False, tts_warmup=False, higgs_prepare_openings=False,
                  speech_cache_enabled=False, recorded_speech_enabled=False,
                  llm_record_metrics=False, dialogue_provider='llama.cpp',
                  llm_url='http://127.0.0.1:8087/v1/chat/completions',
                  higgs_url='http://127.0.0.1:8766/synthesize',
                  stt_device='cpu', stt_compute_type='int8')
    # A copied template must not redirect appraisal to an unmeasured server.
    config.pop('appraisal_llm_url', None)
    config.pop('appraisal_llm_model', None)
    if stage in ('dialogue', 'stt'):
        config['tts_provider'] = 'none'
    if stage == 'stt':
        config['stt_provider'] = 'faster-whisper'
    if stage == 'dialogue':
        config['stt_provider'] = 'none'
        if case == 'batch-128':
            config.update(llm_batch_size=128, llm_ubatch_size=64)
        elif case == 'threads-4':
            config.update(llm_threads=4)
        elif case == 'q8-partial':
            config.update(dialogue_model='gemma-q8', llm_gpu_layers=28 if vram >= 12000 else 20,
                          llm_model_path='.cache/models/gemma4-12b-q8/gemma-4-12B-it-Q8_0.gguf',
                          llm_batch_size=128, llm_ubatch_size=64)
    if stage in ('voice', 'voice-ab', 'combined'):
        config['tts_provider'] = 'higgs'
    if stage == 'voice-ab':
        config['higgs_fast_decode'] = False
    if stage == 'combined':
        config.update(stt_provider='faster-whisper', stt_warmup=True, lip_sync_provider='rhubarb')
        if case == 'nf4-experiment':
            config.update(higgs_quantization='nf4', higgs_allow_quantized_cast=True,
                          llm_gpu_layers=24 if vram >= 12000 else 16)
        else:
            config['llm_gpu_layers'] = 0
    return config


def missing_assets(config, stage):
    missing = []
    if stage in ('dialogue', 'combined'):
        from inference_runtime import launch_description
        desc = launch_description(ROOT, config)
        for path in (Path(desc['executable']), Path(desc['arguments'][1])):
            if not path.is_file():
                missing.append(str(path.relative_to(ROOT)))
    if stage in ('voice', 'voice-ab', 'combined'):
        for relative in (config['higgs_model'], '.cache/higgs-audio-v2-tokenizer', config['higgs_reference']):
            if not (ROOT / relative).exists():
                missing.append(relative)
    if stage in ('stt', 'combined') and not (ROOT / config['stt_model'] / 'model.bin').is_file():
        missing.append(config['stt_model'])
    return missing


def wait_worker(process, timeout):
    deadline = time.monotonic() + timeout
    while process.poll() is None:
        if time.monotonic() > deadline:
            raise TimeoutError('Test stage exceeded time limit; owned processes will be stopped')
        time.sleep(.5)
    if process.returncode:
        raise RuntimeError(f'Test worker exited {process.returncode}; inspect worker.log and any partial report')


def execute_stage(config, stage, folder, args):
    """Own servers in the parent so timeout/failure cleanup also covers server startup."""
    from contextlib import ExitStack
    from inference_runtime import launch_description
    folder.mkdir(parents=True, exist_ok=True)
    config = dict(config, session_log_dir=str(folder / 'sessions'))
    config_path = folder / 'test-config.json'
    save(config_path, config)
    with ExitStack() as stack:
        require_idle()
        starts = {}
        if stage in ('dialogue', 'combined'):
            desc = launch_description(ROOT, config)
            process = stack.enter_context(owned([desc['executable'], *desc['arguments']], folder / 'llama-server.log'))
            starts['llama_seconds'] = wait_health(process, 8087)
        if stage == 'combined':
            process = stack.enter_context(owned([sys.executable, str(ROOT/'services/higgs_service.py'),
                '--config', str(config_path)], folder / 'higgs-server.log'))
            starts['higgs_seconds'] = wait_health(process, 8766)
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--stage', stage,
                   '--config', str(config_path), '--output', str(folder), '--turns', str(args.turns),
                   '--repeats', str(args.repeats)]
        if args.audio:
            command += ['--audio', str(args.audio.resolve())]
        process = stack.enter_context(owned(command, folder / 'worker.log'))
        wait_worker(process, 1800 if stage == 'combined' else 900)
        result = read(folder / 'report.json')
        result['server_startup'] = starts
        save(folder / 'report.json', result)
        return result


def make_plan(mode):
    return {'preflight':[], 'monitor':[],
        'quick':[('dialogue', 'qat-baseline'), ('voice', 'bf16'), ('stt', 'beam-comparison')],
        'tuning':[('dialogue', 'qat-baseline'), ('dialogue', 'batch-128'), ('dialogue', 'threads-4')],
        'voice':[('voice', 'bf16')], 'stt':[('stt', 'beam-comparison')],
        'voice-ab':[('voice-ab', 'bf16-adapter-comparison')],
        'q8':[('dialogue', 'q8-partial')],
        'combined-bf16':[('combined', 'bf16-cpu-dialogue')],
        'combined-nf4':[('combined', 'nf4-experiment')]}[mode]


def write_human_report(output, report):
    lines = ['RTX 3080 PERFORMANCE TEST', 'UTC: ' + report['utc'],
        'Mode: ' + report['mode'], 'Status: ' + report['status'],
        'Current configuration unchanged: ' + str(report.get('config_local_unchanged')),
        'Audible end-to-end <=14s verified: NO', '',
        'Each stage below ran separately unless explicitly labelled combined.',
        'Do not add isolated stage medians to predict combined performance.', '']
    rows = []
    for stage in report['stages']:
        result = stage.get('result', {})
        median = result.get('median_seconds')
        lines.append(f"{stage['name']}: {stage['status']}" + (f'; median {median}s' if median is not None else ''))
        if stage.get('reason'):
            lines.append('  ' + stage['reason'])
        if result.get('warm'):
            lines.append('  Warm summary: ' + json.dumps(result['warm']))
        if 'by_beam' in result:
            lines.append('  CPU STT beam comparison: ' + json.dumps(result['by_beam']))
        if stage['stage'] == 'combined':
            lines.append('  First prepared WAV; microphone endpointing, transport and audible playback excluded.')
            lines.append('  Maximum predicted later extra gap: ' + str(result.get('max_predicted_extra_gap_seconds')))
        rows.append(dict(stage=stage['name'], status=stage['status'], median_seconds=median,
                         p90_seconds=result.get('p90_seconds'), max_seconds=result.get('max_seconds')))
    if report.get('error'):
        lines += ['', 'Error: ' + report['error']]
    lines += ['', 'NEXT STEPS',
        'Read docs/RTX3080_TEST_GUIDE.md for measured baselines, tradeoffs and a 20-turn game test.',
        'QAT Q4 is an optional dialogue precision change; the primary Q8 setting is preserved.',
        'Full QAT GPU dialogue plus BF16 cloned speech exceeds practical 10/12 GB capacity.',
        'NF4 speech is an explicit experiment; compare voice identity and Montenegrin pronunciation.',
        'RTF > 1 means voice generation takes longer than its audio duration for that sample.',
        'Inspect gpu-telemetry.jsonl and logs for memory pressure, retries and thermal/power limits.',
        'Shared allocation alone does not prove paging. nvidia-smi is not a per-process Windows allocation audit.',
        'No driver, power, clock or Windows settings were changed. No model downloads were made.',
        'Reports and WAVs stay on this PC; no automatic upload.', '']
    (output/'REPORT.txt').write_text('\n'.join(lines), encoding='utf-8')
    with (output/'summary.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=['stage', 'status', 'median_seconds', 'p90_seconds', 'max_seconds'])
        writer.writeheader()
        writer.writerows(rows)


def main(args):
    if args.mode == 'combined-nf4' and not args.allow_quantized_voice:
        raise ValueError('NF4 changes voice precision. Add --allow-quantized-voice only for a deliberate quality comparison.')
    if args.mode == 'combined-bf16' and args.gpu_layers is not None:
        raise ValueError('The BF16 combined diagnostic reserves the GPU for speech. Use dialogue-only or NF4 mode for layer sweeps.')
    output = args.output or ROOT/'services/.runtime/rtx3080-tests'/(
        datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output folder must be empty to preserve earlier reports')
    output.mkdir(parents=True, exist_ok=True)
    local = ROOT/'services/config.local.json'
    before = digest(local)
    report = dict(schema_version=1, utc=datetime.now(timezone.utc).isoformat(), mode=args.mode,
                  status='running', stages=[], end_to_end_target_verified=False,
                  synthetic_prompts=True, telemetry_interval_seconds=2,
                  windows_memory_interval_seconds=10, automatic_upload=False)
    print('Reports: ' + str(output), flush=True)
    save(output/'report.json', report)
    try:
        report['hardware'] = hardware()
        save(output/'hardware.json', report['hardware'])
        save(output/'initial-windows-memory.json', windows_memory())
        plan = make_plan(args.mode)
        info = report['hardware']['gpu']
        if plan:
            require_idle()
            if report['hardware'].get('windows', {}).get('game_running'):
                raise RuntimeError('Close AlexPrototype before isolated tests. Use monitor mode to record a running game.')
            if not info['available']:
                raise RuntimeError('nvidia-smi is unavailable; run preflight and repair the NVIDIA/runtime installation first')
            if '3080' not in str(info['values'].get('name')):
                raise RuntimeError('GPU 0 is not an RTX 3080. This test profile is for 3080 10/12 GB only.')
        base = read(args.config or ROOT/'services/config.rtx3080-test.example.json')
        vram = info.get('values', {}).get('memory.total', 0)
        if not isinstance(vram, (int, float)):
            vram = 0
        with Telemetry(output) as telemetry:
            if args.mode == 'monitor':
                telemetry.phase = 'manual-game-test'
                print(f'Recording GPU telemetry for {args.seconds} seconds. Run your usual game conversation now.', flush=True)
                deadline = time.monotonic() + args.seconds
                while time.monotonic() < deadline:
                    time.sleep(.5)
            for stage, case in plan:
                telemetry.phase = case
                config = stage_config(base, stage, case, vram)
                if args.gpu_layers is not None and stage in ('dialogue', 'combined'):
                    config['llm_gpu_layers'] = args.gpu_layers
                row = dict(stage=stage, name=case, status='running')
                report['stages'].append(row)
                save(output/'report.json', report)
                print('Starting ' + case + ' (see worker/server logs for detail)...', flush=True)
                try:
                    missing = missing_assets(config, stage)
                    if missing:
                        row.update(status='skipped', reason='Install required assets first: ' + ', '.join(missing))
                        continue
                    sample = gpu_sample()
                    values = sample.get('values', {})
                    total, used = values.get('memory.total'), values.get('memory.used')
                    free = total-used if all(isinstance(v, (int, float)) for v in (total, used)) else None
                    minimum = 9500 if stage in ('voice', 'voice-ab') or (stage=='combined' and case!='nf4-experiment') else 8000
                    if stage != 'stt' and (free is None or free < minimum):
                        row.update(status='skipped', reason=f'Needs approximately {minimum} MiB free dedicated VRAM for this screening test; observed {free}. Close other GPU applications and rerun.')
                        continue
                    row['result'] = execute_stage(config, stage, output/case, args)
                    row['status'] = 'completed'
                except Exception as exc:
                    row.update(status='failed', reason=f'{type(exc).__name__}: {exc}')
                    # A failed later turn must not hide earlier timings or the
                    # partial benchmark's own completed/target flags.
                    partial = output/case/'report.json'
                    try:
                        if partial.is_file():
                            row['result'] = read(partial)
                    except (OSError, ValueError):
                        row['partial_report_unreadable'] = True
                finally:
                    save(output/'report.json', report)
                    print(case + ': ' + row['status'], flush=True)
        statuses = [row['status'] for row in report['stages']]
        report['status'] = 'failed' if 'failed' in statuses else 'partial' if 'skipped' in statuses else 'completed'
    except KeyboardInterrupt:
        report.update(status='interrupted', error='Interrupted; owned test processes cleaned up')
    except Exception as exc:
        report.update(status='blocked', error=f'{type(exc).__name__}: {exc}')
    finally:
        report['config_local_unchanged'] = digest(local) == before
        try:
            report['ports_after_test'] = occupied_ports()
        except RuntimeError as exc:
            report['ports_after_test'] = None
            report['port_check_error'] = str(exc)
        save(output/'report.json', report)
        write_human_report(output, report)
        with (output/'manual-game-timings.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream)
            writer.writerow(['turn', 'character', 'first_audible_seconds', 'longest_extra_gap_seconds', 'notes'])
            for index in range(1, 21):
                writer.writerow([index, '', '', '', ''])
    print('Finished: ' + report['status'] + '\nRead ' + str(output/'REPORT.txt'), flush=True)
    return 0 if report['status'] == 'completed' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['preflight', 'quick', 'tuning', 'voice', 'voice-ab', 'stt',
                                         'q8', 'combined-bf16', 'combined-nf4', 'monitor'], default='quick')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--config', type=Path, help='Test template only; current local config is never loaded or changed')
    parser.add_argument('--turns', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--gpu-layers', type=int, help='Optional 0-49 layer setting for a deliberate dialogue/NF4 offload sweep')
    parser.add_argument('--audio', type=Path, help='Optional mono PCM16 .2-45 s WAV for STT/combined testing')
    parser.add_argument('--seconds', type=int, default=120, help='Monitor duration')
    parser.add_argument('--allow-quantized-voice', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--stage', choices=['dialogue', 'voice', 'voice-ab', 'stt', 'combined'], help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if not 4 <= arguments.turns <= 40 or not 1 <= arguments.repeats <= 5 or not 10 <= arguments.seconds <= 1800:
        parser.error('Use 4-40 turns, 1-5 repeats and 10-1800 monitor seconds')
    if arguments.audio and not arguments.audio.is_file():
        parser.error('--audio file does not exist')
    if arguments.gpu_layers is not None and not 0 <= arguments.gpu_layers <= 49:
        parser.error('--gpu-layers must be 0-49; 49 requests full Gemma offload in the bundled build')
    if arguments.worker:
        worker(arguments)
    else:
        raise SystemExit(main(arguments))
