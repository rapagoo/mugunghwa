"""Bounded observations for manual ROI/crossing/ID validation, not game verdicts."""
from collections import deque
import math
from .geometry import inside, cross


class VisionValidation:
    def __init__(self, config, session, missing_after=.5):
        self.config, self.session = config, session
        self.missing_after = missing_after
        self.tracks = {}
        self.events = deque(maxlen=60)
        self.sequence = 0
        self.frames = 0
        self.started = None
        self.new_ids = 0
        self.max_visible = 0
        self.intervals = deque(maxlen=300)

    def event(self, kind, tid, media, **details):
        self.sequence += 1
        self.events.append(dict(seq=self.sequence,kind=kind,track_id=tid,media_s=round(media,3),**details))

    def update(self, boxes, ids, confidence, width, height, media, finish, interval_ms=None):
        if self.started is None:
            self.started = media
        self.frames += 1
        if interval_ms is not None:
            self.intervals.append(interval_ms)
        self.max_visible = max(self.max_visible,len(boxes))
        visible = set(ids)
        observations = []
        # Record one gap event after a grace period; a gap is not proof of an ID swap.
        for tid, old in list(self.tracks.items()):
            gap = media-old['last_seen']
            if tid not in visible and gap >= self.missing_after and not old['missing']:
                old['missing'] = True
                self.event('missing',tid,media,gap_s=round(gap,3))
            if gap > 30:
                del self.tracks[tid]
        for index, (x1,y1,x2,y2) in enumerate(boxes):
            tid = ids[index] if index < len(ids) else None
            foot = [(x1+x2)/2/width,y2/height]
            in_roi = inside(foot,self.config['roi']) if self.config else None
            side = distance = None
            if self.config:
                a,b = self.config['finish_line']
                sign = 1 if cross(a,b,self.config['finish_direction_point']) > 0 else -1
                distance = cross(a,b,foot)/math.dist(a,b)*sign
                side = 'line' if abs(distance)<.01 else ('destination' if distance>0 else 'approach')
            event = finish.update(tid,foot,media) if tid is not None and finish else None
            if tid is not None:
                old = self.tracks.get(tid)
                if old is None:
                    if len(self.tracks)>=256:
                        del self.tracks[min(self.tracks,key=lambda key:self.tracks[key]['last_seen'])]
                    self.new_ids += 1
                    self.event('new_id',tid,media)
                else:
                    if old['missing']:
                        self.event('reappeared',tid,media,gap_s=round(media-old['last_seen'],3))
                    if in_roi is not None and old['in_roi'] != in_roi:
                        self.event('roi_enter' if in_roi else 'roi_exit',tid,media)
                self.tracks[tid] = dict(last_seen=media,in_roi=in_roi,missing=False)
                if event:
                    self.event('finish_candidate',tid,media,crossed_at=event['crossed_at'])
            state = finish.states.get(tid,{}) if finish and tid is not None else {}
            observations.append(dict(track_id=tid,foot=[round(v,4) for v in foot],in_roi=in_roi,
                confidence=round(confidence[index],3) if index<len(confidence) else None,
                line_side=side,line_distance=None if distance is None else round(distance,4),
                armed=state.get('armed',False),pending=state.get('pending') is not None,
                candidate=tid in finish.completed if finish and tid is not None else False))
        return dict(session=self.session,frames=self.frames,elapsed_s=round(media-self.started,1),
                    new_id_events=self.new_ids,max_visible=self.max_visible,
                    mean_interval_ms=round(sum(self.intervals)/len(self.intervals),1) if self.intervals else None,
                    observations=observations,events=list(self.events),
                    missing_ids=[tid for tid,old in self.tracks.items() if old['missing']],
                    untracked=len(boxes)-len(ids))
