"""Pi game controller launcher. Server stays separate; no automatic START."""
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:cmd=(proc/'cmdline').read_bytes().split(b'\0')
    except (OSError,PermissionError):continue
    if cmd and Path(os.fsdecode(cmd[0])).name=='iot_client' and b'PI' in cmd:
        raise SystemExit('PI controller already running (PID '+proc.name+'); stop it first.')
folder=root/'.runtime/game';folder.mkdir(parents=True,exist_ok=True)
fifo=folder/'input'
if not fifo.exists():os.mkfifo(fifo,0o600)
fd=os.open(fifo,os.O_RDWR)
with (folder/'controller.log').open('a',buffering=1) as log:
    process=subprocess.Popen([str(root/'pi/controller/iot_client'),'127.0.0.1','5000','PI',
        '--game','--duration','180','--move-seconds','5','--ack-timeout','10'],
        stdin=fd,stdout=log,stderr=log,start_new_session=True)
os.close(fd)
(folder/'controller.pid').write_text(str(process.pid))
print('Game controller launched; wait for HOME, then STM START. Limit 180s; no audio yet.')
