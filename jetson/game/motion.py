"""Box displacement diagnostics and local stop-phase trials; no game authority."""
from collections import deque
import math
import statistics


class MotionTrial:
    def __init__(self):
        self.tracks = {}
        self.version = None
        self.phase = 'idle'
        self.phase_at = 0
        self.events = deque(maxlen=60)

    def update(self, boxes, ids, observations, width, height, now, command):
        if command['version'] != self.version:
            self.version = command['version']
            self.phase, self.phase_at = command['phase'], command['requested_at']
            self.events.clear()
            for state in self.tracks.values():
                state.update(anchor=None, suspect=None, failed=False)
        for tid in list(self.tracks):
            if now-self.tracks[tid]['seen'] > 30:
                del self.tracks[tid]
        output = []
        for i, box in enumerate(boxes):
            tid = ids[i] if i < len(ids) else None
            x1,y1,x2,y2 = box
            # Both axes use height units so aspect ratio does not distort distance.
            point = ((x1+x2)/2/height,(y1+y2)/2/height)
            scale = max((y2-y1)/height,.02)
            status, score = 'pending', None
            state = None
            if tid is not None:
                state = self.tracks.get(tid)
                if state is None:
                    if len(self.tracks) >= 256:
                        del self.tracks[min(self.tracks,key=lambda k:self.tracks[k]['seen'])]
                    state = dict(history=deque(maxlen=40),seen=now,anchor=None,
                                 suspect=None,failed=False,status='pending')
                    self.tracks[tid] = state
                if now-state['seen'] > .5:
                    state['history'].clear()
                    state.update(anchor=None,suspect=None,status='pending')
                state['seen'] = now
                state['history'].append((now,point,scale))
                history = state['history']
                while history and now-history[0][0] > .5:
                    history.popleft()
                if len(history)>=4 and now-history[0][0]>=.25:
                    first = list(history)[:2]
                    last = list(history)[-2:]
                    a = tuple(statistics.mean(v[1][d] for v in first) for d in range(2))
                    b = tuple(statistics.mean(v[1][d] for v in last) for d in range(2))
                    score = math.dist(a,b)/statistics.median(v[2] for v in history)
                    if score >= .035:
                        state['status'] = 'moving'
                    elif score <= .015:
                        state['status'] = 'still'
                    status = state['status']
                in_roi = observations[i]['in_roi']
                eligible = in_roi is True and not observations[i]['candidate']
                if not eligible:
                    state.update(anchor=None,suspect=None)
                if self.phase == 'stop' and now-self.phase_at >= .7 and eligible:
                    if state['anchor'] is None and status != 'pending':
                        state['anchor'] = (point,scale)
                    anchor = state['anchor']
                    if anchor:
                        delta = math.dist(anchor[0],point)/max(anchor[1],scale)
                        if delta >= .06:
                            if state['suspect'] is None:
                                state['suspect'] = now
                            if now-state['suspect'] >= .2 and not state['failed']:
                                state['failed'] = True
                                self.events.append(dict(track_id=tid,kind='stop_motion_candidate',
                                    after_stop_s=round(now-self.phase_at,2),displacement=round(delta,3)))
                        else:
                            state['suspect'] = None
            output.append(dict(track_id=tid,status=status,score=None if score is None else round(score,3),
                stop_candidate=bool(state and state['failed']),
                stop_baseline_ready=bool(state and state['anchor'] is not None)))
        return dict(phase=self.phase,version=self.version,grace_remaining_s=round(max(0,.7-(now-self.phase_at)),2)
                    if self.phase=='stop' else 0,observations=output,events=list(self.events),
                    missing_ids=[tid for tid,s in self.tracks.items() if now-s['seen']>.5],
                    parameters=dict(window_s=.5,moving=.035,still=.015,stop_displacement=.06,
                                    grace_s=.7,confirmation_s=.2,max_gap_s=.5))
