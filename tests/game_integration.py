"""Real C/server/bridge integration with synthetic cached inference; no physical boards."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'jetson'))
from game.web import Monitor, create_server
from cycle_integration import wait_until

@contextmanager
def debug_folder():
    with tempfile.TemporaryDirectory() as directory:
        try: yield directory
        except Exception:
            for log in Path(directory).glob('*.log'):
                print(log.name+'\n'+log.read_text()[-6000:])
            raise


def main():
    class DB:
        def snapshot(self): return {}
    monitor=Monitor('synthetic'); done=threading.Event()
    fixture=dict(ids=[11,22],passed=[],failed=[],epoch=1,revision=1)
    def infer():
        while not done.is_set():
            command=monitor.get_trial()
            monitor.update(dict(state='running',pose={'enabled':True},calibrated=True,
                completed_wall=time.monotonic(),epoch=fixture['epoch'],calibration_revision=fixture['revision'],
                validation=dict(observations=[dict(track_id=i,in_roi=True) for i in fixture['ids']]),
                candidates=[dict(track_id=i,phase=command['phase'],phase_version=command['version']) for i in fixture['passed']],
                pose_trial=dict(phase=command['phase'],version=command['version'],
                    observations=[dict(track_id=i,stop_candidate=True) for i in fixture['failed']])))
            time.sleep(.02)
    worker=threading.Thread(target=infer); worker.start()
    web=create_server('127.0.0.1',0,monitor,DB()); http=threading.Thread(target=web.serve_forever);http.start()
    procs=[]; logs=[]; peers=[]
    try:
        with debug_folder() as tmp:
            tmp=Path(tmp); (tmp/'idpasswd.txt').write_text('PI PASSWD\nJETSON PASSWD\nSTM PASSWD\nARD PASSWD\n')
            audio_error='--audio-error-test' in sys.argv
            audio_test='--audio-test' in sys.argv or audio_error
            env=os.environ.copy()
            if audio_test:
                (tmp/'chant.mp3').touch(); (tmp/'shot.mp3').touch()
                player=tmp/'ffplay'; player.write_text('#!/bin/sh\nsleep 0.6\nexit '+('1' if audio_error else '0')+'\n'); player.chmod(0o700)
                env['PATH']=str(tmp)+os.pathsep+env['PATH']
            def launch(command,name,cwd=ROOT):
                f=(tmp/(name+'.log')).open('w');logs.append(f)
                proc=subprocess.Popen(command,cwd=cwd,stdout=f,stderr=f,stdin=subprocess.PIPE,text=True,env=env)
                procs.append(proc);return proc
            server=launch([str(ROOT/'pi/server/iot_server'),'15003'],'server',tmp);time.sleep(.3)
            ctl=launch([str(ROOT/'pi/controller/iot_client'),'127.0.0.1','15003','PI','--game','--duration','5',
                '--move-seconds','.6','--hold-seconds','.5','--ack-timeout','2','--journal',str(tmp/'events.jsonl'),'--no-db-writer']+(['--audio'] if audio_test else []),'controller')
            bridge=launch([sys.executable,'-u',str(ROOT/'jetson/phase_test_client.py'),'--host','127.0.0.1','--port','15003',
                '--web','http://127.0.0.1:'+str(web.server_port),'--audio-dir',str(tmp)],'bridge')
            received={'STM':[],'ARD':[]}
            def board(name):
                conn=socket.create_connection(('127.0.0.1',15003));conn.sendall(('['+name+':PASSWD]').encode())
                stream=conn.makefile('rb');assert b'New connected!' in stream.readline();peers.append(conn)
                def receive():
                    try:
                        while not done.is_set():
                            line=stream.readline().decode().strip()
                            if not line:break
                            received[name].append(line)
                            if line.startswith('[PI]MOTOR@'):conn.sendall((line+'@OK\n').encode())
                    except OSError:pass
                thread=threading.Thread(target=receive,daemon=True);thread.start()
                return conn
            stm=board('STM');board('ARD')
            def records():
                path=tmp/'events.jsonl'
                return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            def home():wait_until(lambda:(monitor.cycle_snapshot()['cycle'] or {}).get('stage')=='HOME',timeout=9)
            def start():ctl.stdin.write('start\n');ctl.stdin.flush()
            def latest():return records()[-1]
            home();time.sleep(1.1);start()
            wait_until(lambda:records() and latest()['phase']=='move')
            if audio_error:
                wait_until(lambda:latest()['phase']=='aborted')
                assert latest()['reason']=='audio_error'
                assert '[PI]MOTOR@FRONT' not in received['STM']
                home()
                print('Audio error abort/rear recovery passed')
                return
            if audio_test:
                time.sleep(.15)
                assert '[PI]MOTOR@FRONT' not in received['STM'], 'Motor turned before sound completion'
            assert [p['track_id'] for p in latest()['players']]==[11,22]
            fixture['ids']=[11,22,33];fixture['passed']=[11,33]
            wait_until(lambda:latest()['players'][0]['status']=='passed')
            fixture['passed']=[]
            wait_until(lambda:latest()['phase']=='stop')
            fixture['failed']=[11,22,33]
            wait_until(lambda:latest()['phase']=='finished')
            assert [p['status'] for p in latest()['players']]==['passed','failed']
            assert latest()['reason']=='all_resolved'
            for name in received:
                wait_until(lambda:name in received and '[PI]COUNT@2@1@1' in received[name])
                assert any(x.startswith('[PI]TIME@') for x in received[name])
            oldid=latest()['id'];fixture['failed']=[];fixture['ids']=[11,22];home();start()
            wait_until(lambda:latest()['id']!=oldid)
            wait_until(lambda:latest()['phase']=='finished',timeout=8)
            assert latest()['reason']=='timeout' and latest()['remaining']==0
            assert all(p['status']=='failed' for p in latest()['players'])
            home();oldid=latest()['id'];start();wait_until(lambda:latest()['id']!=oldid)
            stm.sendall(b'[PI]STOP\n');wait_until(lambda:latest()['phase']=='aborted')
            assert latest()['reason']=='operator_stop';home()
            count=len(records());fixture['ids']=[];time.sleep(.1);start();time.sleep(.5)
            assert len(records())==count # Empty enrollment creates no game.
            fixture['ids']=[11];time.sleep(.1);start();wait_until(lambda:len(records())>count)
            wait_until(lambda:(monitor.cycle_snapshot()['cycle'] or {}).get('stage')=='PLAY_MOVE')
            fixture['epoch']=2;wait_until(lambda:latest()['phase']=='aborted')
            assert latest()['reason']=='source_changed'
            home();oldid=latest()['id'];start();wait_until(lambda:latest()['id']!=oldid)
            wait_until(lambda:(monitor.cycle_snapshot()['cycle'] or {}).get('stage')=='PLAY_MOVE')
            bridge.terminate();bridge.wait(timeout=3)
            launch([sys.executable,'-u',str(ROOT/'jetson/phase_test_client.py'),'--host','127.0.0.1','--port','15003',
                '--web','http://127.0.0.1:'+str(web.server_port)],'bridge-reconnected')
            wait_until(lambda:latest()['phase']=='aborted')
            assert latest()['reason']=='communication_error'
            print('PASS game: frozen roster, outsider exclusion, immutable/duplicate results, both LCD packets, timeout all fail, STOP, empty roster, source-change and fast bridge restart abort')
    except Exception:
        for name in ('controller','bridge'):
            if 'tmp' in locals() and (tmp/(name+'.log')).exists():print((tmp/(name+'.log')).read_text())
        raise
    finally:
        done.set()
        for peer in peers:peer.close()
        for proc in reversed(procs):
            if proc.poll() is None:proc.terminate();proc.wait(timeout=4)
        for log in logs:log.close()
        worker.join();web.shutdown();web.server_close();http.join()


if __name__=='__main__':main()
