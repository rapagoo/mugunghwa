"""Nonblocking speaker playback; phase bridge remains responsive during sound."""
import os
from pathlib import Path
import subprocess


class Audio:
    def __init__(self, folder, player='ffplay'):
        self.folder = Path(folder)
        self.player = player
        self.chant = None
        self.shot = None
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
        # Limit concurrent shots: several eliminations close together share one shot.
        if self.shot is None or self.shot.poll() is not None:
            if self.shot is not None:
                self.shot.wait()
            self.shot = self.play('shot')
        self.seen.add(key)

    def poll(self):
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
        self.cancel()
        if self.shot is not None:
            if self.shot.poll() is None:
                self.shot.terminate()
            self.shot.wait(timeout=2)
