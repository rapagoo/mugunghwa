"""One capture path for webcam and video, with an explicit media clock."""
import math
from pathlib import Path
import time

import cv2


class FrameSource:
    def __init__(self, camera=0, video=None, loop=False):
        self.video = video
        self.loop = loop
        if video and not Path(video).is_file():
            raise ValueError('Video file does not exist: ' + video)
        self.cap = cv2.VideoCapture(str(video) if video else camera)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError('Cannot open input')
        if not video:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if video and (not math.isfinite(self.fps) or self.fps <= 0):
            self.cap.release()
            raise ValueError('Video FPS unavailable; convert to a constant-frame-rate video')
        self.epoch = 0
        self.index = 0
        self.start = time.monotonic()
        self.previous_time = -1.0

    def restart(self):
        if not self.video:
            return False
        self.cap.release()
        self.cap = cv2.VideoCapture(str(self.video))
        if not self.cap.isOpened():
            raise RuntimeError('Cannot reopen video')
        self.index = 0
        self.previous_time = -1.0
        self.epoch += 1
        return True

    def read(self):
        ok, frame = self.cap.read()
        if not ok and self.video and self.loop:
            self.restart()
            ok, frame = self.cap.read()
        if not ok:
            if self.video:
                return None
            raise RuntimeError('Webcam capture failed')
        timestamp = time.monotonic() - self.start
        if self.video:
            timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if not math.isfinite(timestamp) or timestamp <= self.previous_time:
                timestamp = max(self.index / self.fps, self.previous_time + 1 / self.fps)
            timestamp = max(0, timestamp)
            self.previous_time = timestamp
        self.index += 1
        return frame, timestamp, self.epoch

    def close(self):
        self.cap.release()
