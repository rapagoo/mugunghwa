"""Opt-in TCP-to-local-web phase bridge. No detector instance or MCU commands."""
import argparse
import json
import re
import select
import signal
import socket
import time
from pathlib import Path
from urllib.request import Request, urlopen
from game.game_bridge import enroll, observations
from game.audio import Audio


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


def session(host, port, web, audio=None):
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
        # A reconnected bridge has lost its in-memory game/phase binding.
        # Cancel any old Pi game even if reconnection took less than 3 seconds.
        conn.sendall(b'[PI]TRIAL@ERROR\n')
        apply_phase(web,'IDLE')
        print('PHASE_BRIDGE_READY', flush=True)
        expected = None
        buffer = bytearray()
        last_ping = time.monotonic()
        next_health = 0
        cached = {}
        last_health = None
        game = None
        phase_token = None
        next_observation = 0
        def send(payload):
            conn.sendall(('[PI]'+payload+'\n').encode())
        while True:
            now = time.monotonic()
            completed = audio.poll() if audio else None
            if completed:
                key, ok = completed
                send('AUDIO@{}@{}@{}'.format(key[0],key[1],'DONE' if ok else 'ERROR'))
                print('AUDIO_COMPLETE {} {}'.format(key,ok),flush=True)
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
                    web_json(web, '/api/cycle', {'health':healthy, 'reason':reason or 'ready'})
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
                    try: web_json(web, '/api/cycle', {'health':False, 'reason':health[:200]})
                    except Exception: pass
                    try: apply_phase(web,'IDLE')
                    except Exception: pass
                    expected = None
                next_health = time.monotonic()+1
            if game and now >= next_observation:
                try:
                    state = web_json(web,"/api/vision")
                    if not fresh(state) or state.get("epoch")!=game[1] or state.get("calibration_revision")!=game[2]:
                        send("GAME_ERROR"); game=None
                    elif expected and phase_token:
                        for tid, verdict in observations(state,expected):
                            send("OBS@{}@{}@{}@{}@{}@{}".format(game[0],phase_token,tid,verdict,game[1],game[2]))
                except Exception:
                    send("GAME_ERROR"); game=None
                next_observation=time.monotonic()+.2
            if not select.select([conn],[],[],audio.wait_timeout() if audio else .1)[0]:
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
                report = re.fullmatch(r'\[PI\]CYCLE@([0-9a-f]{8})@([A-Z_]+)@([A-Z_]+)@(\d{1,6})@([A-Z_]+)', text)
                if report:
                    token, stage, motor, remaining, error = report.groups()
                    try:
                        web_json(web, '/api/cycle', dict(token=token,stage=stage,motor=motor,
                            remaining_ms=int(remaining),error=error))
                    except Exception as error:
                        print('CYCLE_REPORT_ERROR '+str(error),flush=True)
                    continue
                join = re.fullmatch(r'\[PI\]JOIN@([0-9a-f]{8})',text)
                if join:
                    token=join.group(1)
                    try:
                        state=web_json(web,'/api/vision')
                        if not fresh(state): raise RuntimeError('Stale inference')
                        ids=enroll(state)
                        send('JOIN_BEGIN@{}@{}@{}@{}'.format(token,len(ids),state['epoch'],state['calibration_revision']))
                        for tid in ids: send('JOIN_PERSON@{}@{}'.format(token,tid))
                        send('JOIN_END@'+token)
                    except Exception:
                        send('JOIN_BEGIN@{}@0@0@0'.format(token))
                    continue
                active = re.fullmatch(r'\[PI\]GAME@([0-9a-f]{32})@(\d+)@(\d+)',text)
                if active:
                    game=(active[1],int(active[2]),int(active[3])); continue
                if text == '[PI]GAME@END':
                    if audio: audio.cancel()
                    game=None; continue
                sound = re.fullmatch(r'\[PI\]AUDIO@([0-9a-f]{32})@([0-9a-f]{8})@CHANT',text)
                if sound:
                    key=(sound[1],sound[2])
                    try:
                        if not audio or not game or game[0]!=key[0]:
                            raise RuntimeError('Audio/game unavailable')
                        audio.start(key)
                        print('AUDIO_CHANT '+str(key),flush=True)
                    except Exception as error:
                        send('AUDIO@{}@{}@ERROR'.format(*key))
                        print('AUDIO_ERROR '+str(error),flush=True)
                    continue
                shot = re.fullmatch(r'\[PI\]SOUND@([0-9a-f]{32})@FAIL@(\d+)',text)
                if shot:
                    if audio and game and game[0]==shot[1]:
                        try: audio.fail((shot[1],'FAIL',shot[2]))
                        except Exception as error: print('SHOT_ERROR '+str(error),flush=True)
                    continue
                if text == '[PI]STOP':
                    expected = apply_phase(web,'IDLE'); continue
                match = re.fullmatch(r'\[PI\]PHASE@(MOVE|STOP|IDLE)@([0-9a-f]{8})',text)
                if not match:
                    continue
                phase, token = match.groups()
                if phase == 'IDLE' and audio: audio.cancel()
                ack = 'PHASE@{}@{}@OK'.format(phase,token)
                if token in cached:
                    if cached[token] == ack: send(ack)
                    continue
                try:
                    expected = apply_phase(web,phase)
                    phase_token = token
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
    parser.add_argument('--audio-dir',default=str(Path(__file__).resolve().parents[1]/'.runtime/audio'))
    args=parser.parse_args()
    def shutdown(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,shutdown)
    audio=Audio(args.audio_dir)
    try:
        while True:
            try: session(args.host,args.port,args.web,audio)
            except (OSError,ValueError,RuntimeError) as error:
                print('BRIDGE_RECONNECT '+str(error),flush=True)
                audio.cancel()
                try: apply_phase(args.web,'IDLE')
                except Exception: pass
                time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        audio.close()
        try: apply_phase(args.web,'IDLE')
        except Exception: pass


if __name__=='__main__':
    main()
