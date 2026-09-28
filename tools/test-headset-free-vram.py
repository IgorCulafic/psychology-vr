"""Synthetic dual-view Unity + live Gemma/BF16 speech stress test, without a headset.

Uses the already-running model and speech services. An isolated bridge/journal
drives actual silent Unity audio playback, lip sync and performance responses.
This does not emulate the OpenXR compositor, Link encoder or a 4090's speed.
"""
import argparse
import base64
import io
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge,make_handler

FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)

def get(url):
    with urllib.request.urlopen(url,timeout=10) as response:return json.load(response)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='docs/generated/headset-free-stress')
    parser.add_argument('--eye-size',type=int,default=3000,choices=[2000,2400,3000])
    parser.add_argument('--turns',type=int,default=6,choices=range(1,7))
    args=parser.parse_args();output=(ROOT/args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'services/config.local.json').read_text(encoding='utf-8-sig'))
    active=get('http://127.0.0.1:8765/models')
    if active['current']!='gemma' or active['switching']:raise RuntimeError('Select Gemma and wait for it to load first.')
    voice=get('http://127.0.0.1:8766/health')
    if voice['quantization']!='bf16' or voice['busy']:raise RuntimeError('Wait for the BF16 voice service to be idle.')
    config['session_log_dir']=str(ROOT/'services/.runtime/headset-free-stress-sessions')
    bridge=Bridge(config)
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(bridge))
    serving=threading.Thread(target=server.serve_forever,daemon=True);serving.start()
    stop=threading.Event();samples=[];phase=['services_idle'];errors=[]
    def monitor():
        while not stop.is_set():
            try:
                raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True,creationflags=FLAGS)
                used,total,util=map(int,raw.strip().splitlines()[0].split(','))
                samples.append(dict(time=time.time(),phase=phase[0],used_mib=used,total_mib=total,gpu_percent=util))
            except Exception as error:errors.append(str(error))
            stop.wait(.5)
    watching=threading.Thread(target=monitor);watching.start()
    stt=[]
    def transcription():
        try:
            import soundfile as sf
            reference=ROOT/config['higgs_reference']
            audio,rate=sf.read(reference,dtype='float32',always_2d=True)
            wav=io.BytesIO();sf.write(wav,audio.mean(axis=1)[:rate*25],rate,format='WAV',subtype='PCM_16')
            encoded=base64.b64encode(wav.getvalue()).decode()
            for i in range(2):
                start=time.monotonic();result=bridge.transcribe(encoded)
                stt.append(dict(pass_number=i+1,seconds=round(time.monotonic()-start,2),recognized=bool(result.get('text','').strip()),device=config['stt_device']))
                print('CPU STT pass '+str(i+1)+' finished.',flush=True)
                if stop.wait(15):break
        except Exception as error:
            stt.append(dict(error=str(error)));print('STT check failed: '+str(error),flush=True)
    player=None;recognizer=None;code=None
    report=dict(gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True,creationflags=FLAGS).strip(),
        dialogue_model='gemma',speech_precision='bf16',stt_device=config['stt_device'],samples=samples,stt=stt,errors=errors,
        limitations=['No active headset, OpenXR compositor or Quest Link encoder.','The GPU is an RTX 5090, not a 4090.','Synthetic independent cameras and rotating HDR/MSAA buffers do not reproduce single-pass stereo exactly.','Whole-device readings include other applications; peak values are sampled, not continuous hardware high-water marks.'])
    log=output/'unity.log';client_report=output/'unity-report.json'
    if client_report.exists():client_report.unlink()
    try:
        time.sleep(5);phase[0]='unity_stress'
        player=subprocess.Popen([str(ROOT/'unity/Builds/Windows/AlexPrototype.exe'),'--desktop','--headset-free-stress',
            '--stress-bridge',f'http://127.0.0.1:{server.server_port}','--stress-report',str(client_report),
            '--stress-eye-size',str(args.eye_size),'--stress-turns',str(args.turns),
            '-screen-width','1280','-screen-height','720','-screen-fullscreen','0','-logFile',str(log)],cwd=ROOT)
        report['unity_pid']=player.pid;print('UNITY_STRESS_PID '+str(player.pid),flush=True)
        deadline=time.monotonic()+1200;ready=False;announced=0
        while player.poll() is None and time.monotonic()<deadline:
            if log.exists():
                text=log.read_text(encoding='utf-8',errors='replace')
                if not ready and 'GPU_STRESS_RENDER_READY' in text:
                    ready=True;print(f'Dual {args.eye_size}x{args.eye_size} rendering ready; starting CPU STT.',flush=True)
                    recognizer=threading.Thread(target=transcription,daemon=True);recognizer.start()
                for line in [line for line in text.splitlines() if line.startswith('GPU_STRESS_TURN ')][announced:]:
                    print(line,flush=True);announced+=1
            time.sleep(1)
        if player.poll() is None:raise TimeoutError('Unity stress run exceeded 20 minutes.')
        code=player.returncode
        if client_report.exists():report['unity']=json.loads(client_report.read_text(encoding='utf-8-sig'))
        if code!=0:raise RuntimeError(f'Unity exited with {code}; inspect {log}')
        if not report.get('unity',{}).get('passed'):raise RuntimeError('Unity stress checks did not pass.')
    except Exception as error:
        errors.append(str(error))
    finally:
        if player and player.poll() is None:player.terminate();player.wait(timeout=15)
        phase[0]='services_after';time.sleep(5);stop.set();watching.join(timeout=5)
        if recognizer:recognizer.join(timeout=60)
        server.shutdown();server.server_close()
        report['exit_code']=code
        report['phases']={p:dict(samples=len(values),min_mib=min(values),median_mib=statistics.median(values),max_mib=max(values))
            for p in sorted(set(s['phase'] for s in samples)) if (values:=[s['used_mib'] for s in samples if s['phase']==p])}
        report['passed']=not errors and report.get('unity',{}).get('passed',False) and len(stt)==2 and all(s.get('recognized') for s in stt)
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('samples',)},ensure_ascii=True,indent=2),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main())
