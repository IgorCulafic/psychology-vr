"""Local, allowlisted model changes; speech stays loaded and history stays intact."""
import json
from pathlib import Path
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]


class ModelSelection:
    def __init__(self, bridge, config_path=None):
        self.bridge = bridge
        self.config_path = Path(config_path).resolve() if config_path else None
        self.catalog = json.loads((ROOT / 'services/dialogue-models.json').read_text(encoding='utf-8'))['models']
        self.switching = False
        self.error = ''
        self.target = ''

    def status(self):
        with self.bridge.lock:
            return dict(current=self.bridge.config.get('dialogue_model', ''), switching=self.switching,
                        target=self.target, error=self.error,
                        enabled=bool(self.config_path) and self.bridge.config['dialogue_provider']=='llama.cpp', models=[
                dict(id=m['id'], label=m['label'], description=m['description'],
                     installed=all((ROOT / m[k]).is_file() for k in ('model_path', 'server_path')))
                for m in self.catalog])

    def select(self, model_id):
        with self.bridge.lock:
            if not self.config_path or self.bridge.config['dialogue_provider'] != 'llama.cpp':
                raise ValueError('Model switching is unavailable for this service.')
            model = next((m for m in self.catalog if m['id'] == model_id), None)
            if not model or not all((ROOT / model[k]).is_file() for k in ('model_path', 'server_path')):
                raise ValueError('That model/runtime is not installed.')
            if self.switching:
                raise ValueError('A model change is already in progress.')
            if any(s.busy or (s.stream and not s.stream['closed']) for s in self.bridge.sessions.values()):
                raise ValueError('Finish or stop the current reply before changing models.')
            if self.bridge.config.get('dialogue_model') == model_id:
                return self.status()
            self.switching, self.target, self.error = True, model_id, ''
            threading.Thread(target=self._change, args=(model_id,), daemon=True).start()
            return self.status()

    def _change(self, model_id):
        try:
            with self.bridge.inference_lock:
                with (ROOT / 'services/.runtime/model-switch.log').open('w', encoding='utf-8') as log:
                    # IDs are allowlisted above. No executable or command supplied by the client.
                    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(ROOT / 'tools/select-model.ps1'), '-Model', model_id,
                        '-Config', str(self.config_path)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=330)
                if result.returncode:
                    raise RuntimeError('Model change failed; see services/.runtime/model-switch.log. Previous model was restored if possible.')
                with self.bridge.lock:
                    self.bridge.config['dialogue_model'] = model_id
                    self.bridge.context_limit = None
                    for session in self.bridge.sessions.values():
                        session.journal.append('dialogue_model_changed', model=model_id)
        except Exception as exc:
            with self.bridge.lock:
                self.error = str(exc)
        finally:
            with self.bridge.lock:
                self.switching = False
