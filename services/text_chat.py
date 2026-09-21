"""Loopback browser conversations using the same patient/response pipeline as VR."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from alex_service import Bridge, ContractError, StaleTurn, ROOT


def make_handler(config):
    inference_lock = threading.Lock()
    bridges = {}
    for language in ('cnr', 'en'):
        bridge = Bridge(dict(config, conversation_language=language, tts_provider='none',
                             lip_sync_provider='none', stt_provider='disabled', session_source='text_chat'))
        bridge.inference_lock = inference_lock
        bridges[language] = bridge
    static = ROOT / 'services/text_chat_web'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No conversation text or session IDs written to access logs.

        def reply(self, status, value, content_type='application/json; charset=utf-8'):
            data = value if isinstance(value, bytes) else json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self):
            host = f'127.0.0.1:{self.server.server_port}'
            return (self.headers.get('Host') == host and
                    self.headers.get('Origin', f'http://{host}') == f'http://{host}' and
                    self.headers.get('Sec-Fetch-Site') not in ('cross-site',))

        def do_GET(self):
            if not self.allowed():
                return self.reply(403, {'error': 'Use the local chat address.'})
            if self.path == '/health':
                return self.reply(200, {'service': 'psychology-text-chat', 'dialogue_provider': config['dialogue_provider']})
            if self.path == '/catalog':
                return self.reply(200, bridges['cnr'].public_catalog())
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/chat.js': ('chat.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path not in files:
                return self.reply(404, {'error': 'Not found'})
            filename, content_type = files[self.path]
            self.reply(200, (static / filename).read_bytes(), content_type)

        def do_POST(self):
            if not self.allowed():
                return self.reply(403, {'error': 'Use the local chat address.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': 'Expected JSON'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    return self.reply(413, {'error': 'Request too large or empty'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ContractError('Expected an object')
                language = data.get('language', 'cnr')
                if language not in ('cnr', 'en'):
                    raise ContractError('Unsupported language')
                bridge = bridges[language]
                key = data.get('session_id')
                if key is not None and not isinstance(key, str):
                    raise ContractError('Invalid session')
                if self.path == '/session':
                    result = bridge.new_session(data.get('scenario_id'), key)
                elif self.path == '/turn':
                    opening = data.get('opening', False)
                    if not isinstance(opening, bool):
                        raise ContractError('Invalid opening flag')
                    result = bridge.turn(key, data.get('text', ''), opening)
                elif self.path == '/interrupt':
                    result = bridge.invalidate(key)
                else:
                    return self.reply(404, {'error': 'Not found'})
                self.reply(200, result)
            except StaleTurn:
                self.reply(409, {'error': 'Reply stopped. Start or send another turn.'})
            except KeyError:
                self.reply(400, {'error': 'Session expired. Start a new conversation.'})
            except (ValueError, TypeError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                self.reply(502, {'error': 'The local model could not complete this reply. Check the model service and try again.'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'services/config.local.json'))
    parser.add_argument('--port', type=int, default=8794)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(config))
    print(f'Text conversations: http://127.0.0.1:{args.port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
