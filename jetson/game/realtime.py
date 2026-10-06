"""Latest-only work handoff and a media clock for offline real-time replay."""
import threading


class LatestFrame:
    def __init__(self):
        self.condition = threading.Condition()
        self.serial = 0
        self.item = None
        self.closed = False

    def publish(self, item):
        with self.condition:
            self.serial += 1
            self.item = item
            self.condition.notify_all()

    def next(self, after):
        with self.condition:
            self.condition.wait_for(lambda: self.closed or self.serial > after)
            return None if self.closed else (self.serial, self.item)

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class ReplayClock:
    def __init__(self, wall_time, media_time=0):
        self.anchor = wall_time - media_time
        self.paused_at = None

    def media(self, wall_time):
        return (self.paused_at if self.paused_at is not None else wall_time) - self.anchor

    def toggle(self, wall_time):
        if self.paused_at is None:
            self.paused_at = wall_time
        else:
            self.anchor += wall_time - self.paused_at
            self.paused_at = None
