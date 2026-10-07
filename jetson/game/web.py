"""LAN monitoring: one cached JPEG for all viewers, read-only game database."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .mariadb_store import DatabaseUnavailable
from .calibration_store import CalibrationConflict


class Monitor:
    def __init__(self, source):
        self.condition = threading.Condition()
        self.jpeg = None
        self.camera_jpeg = None
        self.serial = 0
        self.closed = False
        self.state = dict(source=source, state='preparing', error=None)

    def update(self, data, jpeg=None, camera_jpeg=None):
        with self.condition:
            self.state.update(data)
            if jpeg is not None:
                self.jpeg = jpeg
                self.serial += 1
            if camera_jpeg is not None:
                self.camera_jpeg = camera_jpeg
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            result = dict(self.state)
        completed = result.pop('completed_wall', None)
        result['result_age_ms'] = None if completed is None else round((time.monotonic()-completed)*1000)
        return result

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class GameDatabase:
    """Schema reserved for Pi-confirmed state. Vision never writes game results."""
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY, phase TEXT NOT NULL,
                    started_at TEXT, remaining_seconds INTEGER CHECK(remaining_seconds >= 0),
                    updated_at TEXT NOT NULL, authority TEXT NOT NULL CHECK(authority='PI'));
                CREATE TABLE IF NOT EXISTS participants (
                    game_id TEXT NOT NULL REFERENCES games(id), id TEXT NOT NULL,
                    name TEXT, status TEXT NOT NULL CHECK(status IN ('playing','passed','failed')),
                    updated_at TEXT NOT NULL, PRIMARY KEY(game_id,id));
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id),
                    event_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                    participant_id TEXT, occurred_at TEXT NOT NULL);
            ''')

    def snapshot(self):
        with closing(sqlite3.connect(self.path, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            game = db.execute('SELECT * FROM games ORDER BY updated_at DESC, id DESC LIMIT 1').fetchone()
            if game is None:
                return dict(connected=False, game=None, participants=[], events=[])
            players = db.execute('SELECT * FROM participants WHERE game_id=? ORDER BY id', (game['id'],)).fetchall()
            events = db.execute('SELECT * FROM events WHERE game_id=? ORDER BY id DESC LIMIT 30', (game['id'],)).fetchall()
            return dict(connected=True, game=dict(game), participants=[dict(p) for p in players],
                        events=[dict(e) for e in events])


def create_server(host, port, monitor, database, calibration=None):
    static = Path(__file__).resolve().parents[1] / 'web'

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def send(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = self.path.split('?', 1)[0]
            try:
                if route in ('/', '/app.js', '/style.css', '/calibrate', '/calibrate.js'):
                    name, mime = {'/': ('index.html','text/html; charset=utf-8'),
                                  '/app.js': ('app.js','text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css','text/css; charset=utf-8'),
                                  '/calibrate': ('calibrate.html','text/html; charset=utf-8'),
                                  '/calibrate.js': ('calibrate.js','text/javascript; charset=utf-8')}[route]
                    self.send((static/name).read_bytes(), mime)
                elif route in ('/api/vision', '/api/game'):
                    data = monitor.snapshot() if route == '/api/vision' else database.snapshot()
                    self.send(json.dumps(data, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')
                elif route == '/api/calibration' and calibration is not None:
                    data = calibration.snapshot()
                    state = monitor.snapshot()
                    data['frame_size'] = [state.get('width'), state.get('height')]
                    data['applied_revision'] = state.get('calibration_revision')
                    self.send(json.dumps(data).encode(), 'application/json; charset=utf-8')
                elif route in ('/frame.jpg', '/camera.jpg'):
                    with monitor.condition:
                        jpeg = monitor.jpeg if route == '/frame.jpg' else monitor.camera_jpeg
                    self.send(jpeg or b'Preview preparing', 'image/jpeg' if jpeg else 'text/plain', 200 if jpeg else 503)
                elif route == '/stream.mjpg':
                    self.connection.settimeout(10)
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    serial = -1
                    while True:
                        with monitor.condition:
                            monitor.condition.wait_for(lambda: monitor.closed or monitor.serial != serial, timeout=2)
                            if monitor.closed:
                                break
                            serial, jpeg = monitor.serial, monitor.jpeg
                        if jpeg is not None:
                            self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                                             str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')
                            self.wfile.flush()
                    self.close_connection = True
                else:
                    self.send(b'Not found', 'text/plain', 404)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                self.close_connection = True
            except (sqlite3.Error, DatabaseUnavailable):
                self.send(b'Database unavailable', 'text/plain', 503)

        def do_POST(self):
            if self.path != '/api/calibration' or calibration is None:
                self.send(b'Not found', 'text/plain', 404)
                return
            # JSON + same-origin browser request, not form submissions from other sites.
            if (self.headers.get('Content-Type', '').split(';')[0] != 'application/json'
                    or self.headers.get('X-Mugunghwa-Calibration') != '1'):
                self.close_connection = True
                self.send(b'JSON calibration request required', 'text/plain', 403)
                return
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.close_connection = True
                self.send(b'Origin mismatch', 'text/plain', 403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    raise ValueError('Invalid request length')
                self.connection.settimeout(5)
                body = json.loads(self.rfile.read(length))
                state = monitor.snapshot()
                if not state.get('width') or not state.get('height'):
                    self.send(b'Camera preparing', 'text/plain', 409)
                    return
                data = calibration.save(body['config'], body['expected_revision'],
                                        state['width'], state['height'])
                self.send(json.dumps(data).encode(), 'application/json; charset=utf-8')
            except CalibrationConflict as error:
                self.send(str(error).encode(), 'text/plain; charset=utf-8', 409)
            except (ValueError, KeyError, TypeError):
                self.close_connection = True
                self.send('설정 형식·영역·결승선·화면 비율을 확인해 주세요.'.encode(), 'text/plain; charset=utf-8', 400)
            except OSError:
                self.send(b'Calibration storage unavailable', 'text/plain', 503)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server

