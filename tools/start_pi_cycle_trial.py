"""Launch opt-in PI trial controller, with a local operator FIFO (no autostart)."""
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
folder=root/'.runtime/cycle-test'
folder.mkdir(parents=True,exist_ok=True)
pidfile=folder/'controller.pid'
if pidfile.exists():
    pid=int(pidfile.read_text())
    proc=Path('/proc')/str(pid)/'cmdline'
    if proc.exists() and b'--cycle-test' in proc.read_bytes():
        raise SystemExit('Trial controller already running')
fifo=folder/'input'
if not fifo.exists():os.mkfifo(fifo,0o600)
fd=os.open(fifo,os.O_RDWR)
with open(folder/'controller.log','a',buffering=1) as log:
    process=subprocess.Popen([str(root/'pi/controller/iot_client'),'127.0.0.1','5000','PI',
        '--cycle-test','--hold-seconds','5','--ack-timeout','10'],stdin=fd,
        stdout=log,stderr=log,start_new_session=True)
os.close(fd)
pidfile.write_text(str(process.pid))
print('Trial ready: STM START button, or printf "start\\n" > '+str(fifo))
