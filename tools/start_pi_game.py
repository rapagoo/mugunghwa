"""Pi game controller launcher. Server stays separate; no automatic START."""
import argparse
import os
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description='Start the Pi game controller without starting a match.')
parser.add_argument('--duration',type=int,default=180,help='Game limit in seconds (1..3600; default: 180).')
parser.add_argument('--no-audio',action='store_true',help='Use fixed movement time instead of speaker playback.')
args=parser.parse_args()
if not 1 <= args.duration <= 3600:
    parser.error('--duration must be 1..3600 seconds')

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
        '--game','--duration',str(args.duration),'--move-seconds','5','--ack-timeout','10'] + ([] if args.no_audio else ['--audio']),
        stdin=fd,stdout=log,stderr=log,start_new_session=True)
os.close(fd)
(folder/'controller.pid').write_text(str(process.pid))
print('Game controller launched; wait for HOME, then STM START. Limit {}s; audio {}.'.format(args.duration, 'off' if args.no_audio else 'on'))
