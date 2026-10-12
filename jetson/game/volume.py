"""USB speaker master volume, independent of game timing and playback."""
import json
import os
from pathlib import Path
import re
import subprocess
import threading

SINK='alsa_output.usb-Generic_USB2.0_Device_20130100ph0-00.analog-stereo'

class VolumeUnavailable(Exception):
    pass

class SpeakerVolume:
    def __init__(self, store):
        self.store=Path(store)
        self.lock=threading.RLock()
        self.restored=False
        self.saved=None
        try:
            data=json.loads(self.store.read_text(encoding='utf-8'))
            self.validate(data)
            if set(data)=={'volume','muted'}: self.saved=data
        except (OSError,ValueError,TypeError): pass

    @staticmethod
    def validate(body):
        if not isinstance(body,dict) or not body or not set(body)<= {'volume','muted'}:
            raise ValueError('Expected volume or muted')
        if 'volume' in body and (type(body['volume']) is not int or not 0<=body['volume']<=100):
            raise ValueError('Volume must be 0..100')
        if 'muted' in body and type(body['muted']) is not bool:
            raise ValueError('Muted must be boolean')

    def _run(self, *args):
        env=os.environ.copy()
        env['LC_ALL']='C'
        env.setdefault('XDG_RUNTIME_DIR','/run/user/{}'.format(getattr(os,'getuid',lambda:1000)()))
        try:
            return subprocess.run(['pactl']+list(args),env=env,capture_output=True,text=True,
                                  check=True,timeout=2).stdout
        except (OSError,subprocess.SubprocessError):
            raise VolumeUnavailable('USB speaker unavailable') from None

    def _read(self):
        # PulseAudio 13 has no get-sink-volume or JSON output.
        for block in re.split(r'(?m)^Sink #',self._run('list','sinks')):
            if not re.search(r'(?m)^\s*Name: '+re.escape(SINK)+r'\s*$',block): continue
            volume=re.search(r'(?m)^\s*Volume: (.*)$',block)
            mute=re.search(r'(?m)^\s*Mute: (yes|no)\s*$',block)
            levels=re.findall(r'(\d+)%',volume.group(1)) if volume else []
            if levels and mute:
                return dict(volume=min(100,max(map(int,levels))),muted=mute.group(1)=='yes')
        raise VolumeUnavailable('USB speaker unavailable')

    def _apply(self, values):
        if 'volume' in values:self._run('set-sink-volume',SINK,str(values['volume'])+'%')
        if 'muted' in values:self._run('set-sink-mute',SINK,'1' if values['muted'] else '0')

    def snapshot(self):
        with self.lock:
            current=self._read()
            if not self.restored:
                if self.saved:self._apply(self.saved);current=self._read()
                self.restored=True
            return current

    def update(self, body):
        self.validate(body)
        with self.lock:
            self.snapshot()
            self._apply(body)
            current=self._read()
            try:
                self.store.parent.mkdir(parents=True,exist_ok=True)
                temporary=self.store.with_suffix('.tmp')
                temporary.write_text(json.dumps(current),encoding='utf-8')
                temporary.replace(self.store)
            except OSError:
                raise VolumeUnavailable('Volume changed but could not save settings') from None
            self.saved=current
            return current
