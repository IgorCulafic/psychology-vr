"""Exercise HTTP delivery with real local TTS/alignment and scripted dialogue."""
import json,sys,threading,urllib.request,wave,io
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'services'))
from alex_service import Bridge,make_handler,validate_mouth_cues
config=json.loads((ROOT/'services/config.local.json').read_text())
config['dialogue_provider']='scripted'
bridge=Bridge(config)
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(bridge))
worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
url=f'http://127.0.0.1:{server.server_port}'
def post(path,body):
    request=urllib.request.Request(url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
try:
    key=post('/session',{})['session_id'];reply=post('/turn',{'session_id':key,'text':'How are you feeling?'})
    for segment in reply['segments']:
        assert segment['lip_sync_source']=='rhubarb' and segment['mouth_cues']
        with urllib.request.urlopen(url+segment['audio_url']) as response:audio=response.read()
        with wave.open(io.BytesIO(audio)) as wav:duration=wav.getnframes()/wav.getframerate()
        validate_mouth_cues(segment['mouth_cues'],duration)
    assert 'mouth_cues' not in bridge.sessions[key].history[-1]['content']
    (ROOT/'docs/generated/facial-service-check.json').write_text(json.dumps({'passed':True,'dialogue_provider':reply['dialogue_provider'],
        'tts_provider':reply['tts_provider'],'total_ms':reply['total_ms'],
        'cue_counts':[len(s['mouth_cues']) for s in reply['segments']]},indent=2))
    post('/reset',{'session_id':key})
    print('FACIAL_SERVICE_OK: real Kokoro + Rhubarb via HTTP; scripted dialogue')
finally:
    server.shutdown();server.server_close();worker.join()
