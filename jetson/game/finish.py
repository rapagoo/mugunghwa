"""Directed finite-line crossing candidates, using provisional track foot points."""
import math
from game.geometry import cross, inside


class FinishDetector:
    def __init__(self, config, margin=0.01, max_gap=0.5):
        self.config = config
        self.a, self.b = config['finish_line']
        self.length = math.dist(self.a, self.b)
        self.sign = 1 if cross(self.a, self.b, config['finish_direction_point']) > 0 else -1
        self.margin, self.max_gap = margin, max_gap
        self.states, self.completed = {}, {}

    def update(self, track_id, foot, timestamp):
        if track_id in self.completed:
            return None
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in foot):
            self.states.pop(track_id, None)
            return None
        distance = cross(self.a, self.b, foot) / self.length * self.sign
        in_roi = inside(foot, self.config['roi'])
        old = self.states.get(track_id)
        if old is None or not 0 < timestamp - old['time'] <= self.max_gap:
            old = dict(armed=False, pending=None)
        armed = old['armed'] or (in_roi and distance <= -self.margin)
        pending = old['pending']
        if pending is not None and distance < 0:
            pending = None
        if armed and 'foot' in old and old['distance'] <= 0 < distance:
            # A crossing of the infinite extension is not a crossing of the line segment.
            p = old['foot']
            da, db = cross(p, foot, self.a), cross(p, foot, self.b)
            if da * db <= 0:
                ratio = old['distance'] / (old['distance'] - distance)
                intersection = [p[i] + ratio * (foot[i] - p[i]) for i in (0, 1)]
                if inside(intersection, self.config['roi']):
                    pending = old['time'] + ratio * (timestamp - old['time'])
        self.states[track_id] = dict(time=timestamp, foot=foot, distance=distance,
                                     armed=armed, pending=pending)
        if pending is not None and in_roi and distance >= self.margin:
            event = dict(track_id=track_id, crossed_at=pending, confirmed_at=timestamp)
            self.completed[track_id] = event
            return event
        return None
