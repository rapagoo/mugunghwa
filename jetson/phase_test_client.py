"""Opt-in TCP-to-local-web phase bridge. No detector instance or MCU commands."""
import argparse
import json
import re
import select
import signal
import socket
import time
from urllib.request import Request, urlopen


def web_json(web, path, body=None):
    req = Request(web+path, data=None if body is None else json.dumps(body).encode(),
        headers={} if body is None else {'Content-Type':'application/json',
            'X-Mugunghwa-Calibration':'1'})
    with urlopen(req, timeout=2) as response:
        return json.load(response)


def fresh(state):
    return (state.get('state') == 'running' and state.get('result_age_ms') is not None
            and state['result_age_ms'] <= 2000 and state.get('pose', {}).get('enabled'))


def apply_phase(web, phase):
    local = {'MOVE':'move', 'STOP':'stop', 'IDLE':'idle'}[phase]
    if phase != 'IDLE' and not fresh(web_json(web, '/api/vision')):
        raise RuntimeError('Fresh pose inference required')
    if phase == 'MOVE':
        # Local trial candidates, not DB/game results; avoid stale finish exclusions.
        web_json(web, '/api/validation/reset', {})
    command = web_json(web, '/api/validation/phase', {'phase':local})
    if phase == 'IDLE':
        return command
    deadline = time.monotonic()+2
    while time.monotonic() < deadline:
        state = web_json(web, '/api/vision')
        trial = state.get('pose_trial', {})
        if fresh(state) and trial.get('version') == command['version'] and trial.get('phase') == local:
            return command
        time.sleep(.05)
    raise RuntimeError('Phase not applied by inference')


def session(host, port, web):
    with socket.create_connection((host, port), timeout=5) as conn:
        conn.sendall(b'[JETSON:PASSWD]')
        reply = bytearray()
        while not reply.endswith(b'\n'):
            part = conn.recv(1)
            if not part or len(reply) >= 100:
                raise RuntimeError('Login reply failed')
            reply.extend(part)
        if b'[JETSON] New connected!' not in reply:
            raise RuntimeError('JETSON login rejected; close another JETSON client')
        conn.settimeout(2)
        apply_phase(web,'IDLE')
        print('PHASE_BRIDGE_READY', flush=True)
        expected = None
        buffer = bytearray()
        last_ping = time.monotonic()
        next_health = 0
        cached = {}
        last_health = None
        def send(payload):
            conn.sendall(('[PI]'+payload+'\n').encode())
        while True:
            now = time.monotonic()
            if now >= next_health:
                try:
                    state = web_json(web,'/api/vision')
                    trial = state.get('pose_trial', {})
                    reason = ('pose inference unavailable or stale' if not fresh(state)
                              else 'Pi heartbeat missing' if now-last_ping > 3 else None)
                    if expected and expected['phase'] != 'idle':
                        if trial.get('phase') != expected['phase'] or trial.get('version') != expected['version']:
                            reason = reason or 'web phase changed outside Pi controller'
                    healthy = reason is None
                    health = reason or 'ready'
                    if health != last_health:
                        print('HEALTH '+health, flush=True); last_health = health
                    send('TRIAL@READY' if healthy else 'TRIAL@ERROR')
                    if not healthy and expected:
                        apply_phase(web,'IDLE'); expected = None
                except Exception as error:
                    health = 'web/communication error: '+str(error)
                    if health != last_health:
                        print('HEALTH '+health, flush=True); last_health = health
                    send('TRIAL@ERROR')
                    try: apply_phase(web,'IDLE')
                    except Exception: pass
                    expected = None
                next_health = time.monotonic()+1
            if not select.select([conn],[],[],.1)[0]:
                continue
            chunk = conn.recv(256)
            if not chunk:
                raise RuntimeError('Pi server disconnected')
            buffer.extend(chunk)
            while b'\n' in buffer:
                line, _, rest = buffer.partition(b'\n'); buffer = bytearray(rest)
                if len(line) >= 100:
                    raise RuntimeError('Oversized message')
                text = line.decode('ascii').rstrip('\r')
                if text == '[PI]TRIAL@PING':
                    last_ping = time.monotonic(); continue
                if text == '[PI]STOP':
                    expected = apply_phase(web,'IDLE'); continue
                match = re.fullmatch(r'\[PI\]PHASE@(MOVE|STOP|IDLE)@([0-9a-f]{8})',text)
                if not match:
                    continue
                phase, token = match.groups()
                ack = 'PHASE@{}@{}@OK'.format(phase,token)
                if token in cached:
                    if cached[token] == ack: send(ack)
                    continue
                try:
                    expected = apply_phase(web,phase)
                    cached[token] = ack
                    if len(cached)>64: del cached[next(iter(cached))]
                    send(ack); print('APPLIED '+ack,flush=True)
                except Exception as error:
                    send('TRIAL@ERROR'); print('PHASE_ERROR '+str(error),flush=True)
            if len(buffer)>=100:
                raise RuntimeError('Unterminated oversized message')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='10.10.16.90')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--web',default='http://127.0.0.1:8080')
    args=parser.parse_args()
    def shutdown(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,shutdown)
    try:
        while True:
            try: session(args.host,args.port,args.web)
            except (OSError,ValueError,RuntimeError) as error:
                print('BRIDGE_RECONNECT '+str(error),flush=True)
                try: apply_phase(args.web,'IDLE')
                except Exception: pass
                time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        try: apply_phase(args.web,'IDLE')
        except Exception: pass


if __name__=='__main__':
    main()
