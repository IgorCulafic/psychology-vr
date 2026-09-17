"""Serve the selected Qwen on loopback without changing other AI installations."""
from pathlib import Path
import socket
import subprocess
import sys
import json

root=Path(__file__).resolve().parents[1]
executable=root/'.tools/llama/llama-server.exe'
model=root/'.cache/models/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf'
if not executable.is_file() or not model.is_file():
    sys.exit('Download the runtime and model first; see README.md.')
with socket.socket() as probe:
    if probe.connect_ex(('127.0.0.1',8087))==0:
        sys.exit('Port 8087 is already in use. Stop the previous project model server before starting another.')
args=[str(executable),'--model',str(model),'--alias','alex-qwen','--host','127.0.0.1','--port','8087',
      '--ctx-size','4096','--parallel','1','--n-gpu-layers','99','--batch-size','256','--ubatch-size','128',
      '--jinja','--reasoning','off','--chat-template-kwargs',json.dumps({'enable_thinking':False}),
      '--spec-type','none']
raise SystemExit(subprocess.call(args,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
