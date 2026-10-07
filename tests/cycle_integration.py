"""Pi-only isolated C/server/real phase bridge/HTTP integration; no physical motors."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'jetson'))
from game.web import Monitor, create_server


def wait_until(predicate, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.03)
    raise AssertionError('Condition timed out')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller',default=str(ROOT/'pi/controller/iot_client'))
    parser.add_argument('--port',type=int,default=15001)
    args=parser.parse_args()
    class Database:
        def snapshot(self):return {}
    monitor=Monitor('simulated')
    finished=threading.Event()
    def inference():
        while not finished.is_set():
            cmd=monitor.get_trial()
            monitor.update(dict(state='running',pose={'enabled':True},completed_wall=time.monotonic(),
                pose_trial=dict(version=cmd['version'],phase=cmd['phase'])))
            time.sleep(.02)
    worker=threading.Thread(target=inference);worker.start()
    web=create_server('127.0.0.1',0,monitor,Database())
    http=threading.Thread(target=web.serve_forever);http.start()
    with tempfile.TemporaryDirectory(prefix='cycle-integration-') as folder:
        folder=Path(folder);(folder/'idpasswd.txt').write_text('PI PASSWD\nJETSON PASSWD\nSTM PASSWD\n')
        processes=[];conn=None
        logs=[]
        try:
            serverlog=open(folder/'server.log','w');logs.append(serverlog)
            server=subprocess.Popen([str(ROOT/'pi/server/iot_server'),str(args.port)],cwd=folder,stdout=serverlog,stderr=serverlog);processes.append(server)
            time.sleep(.3)
            ctlpath=folder/'controller.log';ctl=open(ctlpath,'w');logs.append(ctl)
            controller=subprocess.Popen([args.controller,'127.0.0.1',str(args.port),'PI','--cycle-test','--hold-seconds','.4','--ack-timeout','1.5'],stdin=subprocess.PIPE,stdout=ctl,stderr=ctl,text=True);processes.append(controller)
            wait_until(lambda:'CYCLE READY' in ctlpath.read_text())
            bl=open(folder/'bridge.log','w');logs.append(bl)
            bridge=subprocess.Popen([sys.executable,'-u',str(ROOT/'jetson/phase_test_client.py'),'--host','127.0.0.1','--port',str(args.port),'--web','http://127.0.0.1:'+str(web.server_port)],stdout=bl,stderr=bl);processes.append(bridge)
            conn=socket.create_connection(('127.0.0.1',args.port),timeout=3);conn.sendall(b'[STM:PASSWD]');stream=conn.makefile('rb');assert b'New connected!' in stream.readline()
            time.sleep(1.3)
            def start():controller.stdin.write('start\n');controller.stdin.flush()
            def expect(data):
                line=stream.readline();assert line==data,(line,data)
            # Normal cycle, wrong direction and duplicate ACK cannot advance state.
            start();expect(b'[PI]MOTOR@FRONT\n')
            wait_until(lambda:(monitor.cycle_snapshot()['cycle'] or {}).get('motor')=='FRONT_WAIT')
            conn.sendall(b'[JETSON]PHASE@STOP@deadbeef\n');time.sleep(.1)
            conn.sendall(b'[JETSON]CYCLE@deadbeef@DONE@REAR_OK@0@NONE\n');time.sleep(.1)
            assert monitor.cycle_snapshot()['cycle']['motor']=='FRONT_WAIT'
            assert monitor.get_trial()['phase']=='move'  # STM cannot impersonate PI.
            conn.sendall(b'[PI]MOTOR@REAR@OK\n');time.sleep(.1)
            assert monitor.get_trial()['phase']=='move'
            conn.sendall(b'[PI]MOTOR@FRONT@');time.sleep(.03);conn.sendall(b'OK\n[PI]MOTOR@FRONT@OK\n')
            wait_until(lambda:monitor.get_trial()['phase']=='stop')
            expect(b'[PI]MOTOR@REAR\n');assert monitor.get_trial()['phase']=='stop'
            conn.sendall(b'[PI]MOTOR@REAR@OK\n')
            wait_until(lambda:'CYCLE DONE' in ctlpath.read_text());assert monitor.get_trial()['phase']=='move'
            wait_until(lambda:(monitor.cycle_snapshot()['cycle'] or {}).get('stage')=='DONE')
            assert monitor.cycle_snapshot()['cycle']['motor']=='REAR_OK'
            # Missing motor ACK aborts rather than issuing REAR.
            start();expect(b'[PI]MOTOR@FRONT\n')
            wait_until(lambda:'completion timeout' in ctlpath.read_text())
            wait_until(lambda:monitor.get_trial()['phase']=='idle')
            # Operator stop, then a late completion must not restart STOP.
            start();expect(b'[PI]MOTOR@FRONT\n')
            controller.stdin.write('stop\n');controller.stdin.flush()
            wait_until(lambda:'operator stop' in ctlpath.read_text())
            conn.sendall(b'[PI]MOTOR@FRONT@OK\n');time.sleep(.3)
            assert monitor.get_trial()['phase']=='idle'
            # Loss of Pi pings must clear Jetson's active phase.
            start();expect(b'[PI]MOTOR@FRONT\n');conn.sendall(b'[PI]MOTOR@FRONT@OK\n')
            wait_until(lambda:monitor.get_trial()['phase']=='stop')
            controller.terminate();controller.wait(timeout=3)
            wait_until(lambda:monitor.get_trial()['phase']=='idle',timeout=5)
            wait_until(lambda:not monitor.cycle_snapshot()['healthy'],timeout=5)
            print('PASS cycle: real C + TCP server + Python bridge + HTTP applied phase; wrong/duplicate/split ACK, timeout, stop/late ACK, Pi heartbeat loss')
        finally:
            if conn:conn.close()
            for proc in reversed(processes):
                if proc.poll() is None:proc.terminate();proc.wait(timeout=4)
            for log in logs:log.close()
            print((folder/'controller.log').read_text())
            print((folder/'bridge.log').read_text())
            finished.set();worker.join();web.shutdown();web.server_close();http.join()


if __name__=='__main__':main()
