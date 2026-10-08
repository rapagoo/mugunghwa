"""Pi LCD-only terminal test. Temporarily takes the exclusive PI login.

Keeps the doll at REAR; never sends START or FRONT. Restore the controller after exit.
"""
import argparse
import math
import select
import socket
import time


def run(host, port, step_seconds=0):
    with socket.create_connection((host,port),timeout=3) as conn:
        conn.sendall(b'[PI:PASSWD]')
        stream=conn.makefile('rb')
        reply=stream.readline()
        if b'[PI] New connected!' not in reply:
            raise RuntimeError('PI login failed')
        stream.close()
        conn.settimeout(3)
        buffer=bytearray();last_ping=0
        def send(target,payload):
            text='['+target+']'+payload
            conn.sendall((text+'\n').encode())
            if payload!='TRIAL@PING':print('TX',text,flush=True)
        def wait(expected,seconds=8):
            nonlocal buffer,last_ping
            received=set();deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if time.monotonic()-last_ping>=1:
                    send('JETSON','TRIAL@PING');last_ping=time.monotonic()
                if not select.select([conn],[],[],.1)[0]:continue
                chunk=conn.recv(1024)
                if not chunk:raise RuntimeError('PI connection replaced/disconnected; test stopped')
                buffer.extend(chunk)
                while b'\n' in buffer:
                    line,_,rest=buffer.partition(b'\n');buffer=bytearray(rest)
                    text=line.decode(errors='replace').rstrip('\r')
                    if text.startswith(('[STM]','[ARD]')):print('RX',text,flush=True)
                    if text in expected:received.add(text)
                if received==set(expected):break
            for text in expected:
                print(('PASS ' if text in received else 'MISSING ')+text,flush=True)
            return received==set(expected)
        send('JETSON','STOP')
        rear_ready=False
        for attempt in range(3):
            send('STM','MOTOR@REAR')
            if wait(['[STM]MOTOR@REAR@OK']):
                rear_ready=True
                break
            print('Waiting for STM after reset; retrying rear request.',flush=True)
        if not rear_ready:
            print('Rear completion missing; LCD-only test still sends no FRONT/START.',flush=True)
        results=[]
        for payload in ('COUNT@2@0@0','TIME@180','TIME@179','COUNT@2@1@0','COUNT@2@1@1','TIME@0'):
            for board in ('STM','ARD'):send(board,payload)
            results.append(wait(['['+board+']APPLIED@'+payload for board in ('STM','ARD')]))
            if step_seconds:
                print('DISPLAY_HOLD',step_seconds,'seconds',flush=True)
                time.sleep(step_seconds)
        # Restore neutral LCD data, leaving the doll facing rear.
        for board in ('STM','ARD'):send(board,'COUNT@0@0@0')
        results.append(wait(['['+board+']APPLIED@COUNT@0@0@0' for board in ('STM','ARD')]))
        print('LCD_TEST_RESULT', 'PASS' if all(results) else 'ACK_MISSING',flush=True)
        return all(results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--step-seconds',type=float,default=0,
        help='hold each applied test value for visual LCD inspection (0..10)')
    args=parser.parse_args()
    if not math.isfinite(args.step_seconds) or not 0 <= args.step_seconds <= 10:
        parser.error('--step-seconds must be 0..10')
    raise SystemExit(0 if run(args.host,args.port,args.step_seconds) else 1)
