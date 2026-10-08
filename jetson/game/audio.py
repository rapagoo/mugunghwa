"""Nonblocking speaker playback; phase bridge remains responsive during sound."""
import os
from pathlib import Path
import subprocess
from collections import deque


class Audio:
    def __init__(self, folder, player='ffplay'):
        self.folder = Path(folder)
        self.player = player
        self.chant = None
        self.shot = None
        self.shot_queue = deque()
        self.key = None
        self.seen = set()

    def play(self, name):
        path = self.folder / (name + '.mp3')
        if not path.is_file():
            raise RuntimeError('Missing sound: ' + str(path))
        env = os.environ.copy()
        env.setdefault('XDG_RUNTIME_DIR', '/run/user/{}'.format(os.getuid()))
        return subprocess.Popen([self.player, '-nodisp', '-autoexit', '-loglevel', 'error',
                                 '-i', str(path)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, env=env)

    def start(self, key):
        if key in self.seen:
            return
        self.cancel()
        self.chant = self.play('chant')
        self.key = key
        self.seen.add(key)
        if len(self.seen) > 1024:
            self.seen = {key}

    def fail(self, key):
        if key in self.seen:
            return
        self.seen.add(key)
        self.shot_queue.append(key)
        self.advance_shots()

    def advance_shots(self):
        if self.shot is not None:
            if self.shot.poll() is None:
                return
            if self.shot.wait() != 0:
                print('SHOT_ERROR player exited unsuccessfully', flush=True)
            self.shot = None
        while self.shot_queue:
            key = self.shot_queue.popleft()
            try:
                self.shot = self.play('shot')
                print('SHOT_START '+str(key), flush=True)
                return
            except (OSError, RuntimeError) as error:
                print('SHOT_ERROR {} {}'.format(key,error), flush=True)

    def poll(self):
        self.advance_shots()
        if self.chant is not None and self.chant.poll() is not None:
            result = (self.key, self.chant.wait() == 0)
            self.chant = None
            self.key = None
            return result

    def cancel(self):
        if self.chant is not None:
            if self.chant.poll() is None:
                self.chant.terminate()
            self.chant.wait(timeout=2)
        self.chant = None
        self.key = None

    def close(self):
        self.shot_queue.clear()
        self.cancel()
        if self.shot is not None:
            if self.shot.poll() is None:
                self.shot.terminate()
            self.shot.wait(timeout=2)
