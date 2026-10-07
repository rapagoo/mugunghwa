"""Fixed-pose local stop trial. No participant reassociation or game authority."""
from collections import deque
import math


class PoseMotionTrial:
    JOINTS = (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
    TORSO = (5, 6, 11, 12)

    def __init__(self):
        self.version = None
        self.phase = 'idle'
        self.states = {}
        self.events = deque(maxlen=60)

    @classmethod
    def points(cls, person):
        return {j: tuple(person[j][:2]) for j in cls.JOINTS
                if len(person) == 17 and person[j][2] >= .5
                and all(math.isfinite(v) for v in person[j])}

    @classmethod
    def usable(cls, points):
        return len(points) >= 4 and sum(j in points for j in cls.TORSO) >= 2

    def update(self, boxes, ids, observations, keypoints, now, command):
        changed = command['version'] != self.version
        if changed:
            self.version = command['version']
            self.phase = command['phase']
            self.states.clear()
            self.events.clear()
        # A captured frame predating the command cannot establish its baseline.
        initialize = changed and now >= command['requested_at']
        if changed and not initialize:
            self.version = None
        output = []
        for i, box in enumerate(boxes):
            tid = ids[i] if i < len(ids) else None
            person = keypoints[i] if keypoints is not None and i < len(keypoints) else []
            points = self.points(person)
            eligible = observations[i]['in_roi'] is True and not observations[i]['candidate']
            if initialize and self.phase == 'stop' and tid is not None and eligible:
                self.states[tid] = dict(anchor=points if self.usable(points) else None,
                    scale=max(box[3]-box[1], 1), seen=now, suspect=None,
                    count=0, failed=False, interrupted=False)
            state = self.states.get(tid)
            status, reason, score, joint = 'hold', 'baseline_missing', None, None
            common = {}
            if self.phase != 'stop':
                status, reason = ('allowed', 'move') if self.phase == 'move' else ('idle', 'idle')
            elif keypoints is None:
                reason = 'pose_unavailable'
            elif not eligible:
                reason = 'outside_or_finished'
                if state:
                    state['interrupted'] = True
            elif state and state['anchor']:
                if now-state['seen'] > .5:
                    state['interrupted'] = True
                if state['interrupted']:
                    reason = 'tracking_gap'
                else:
                    common = {j: math.dist(state['anchor'][j], p)/state['scale']
                              for j, p in points.items() if j in state['anchor']}
                    if not self.usable(common):
                        reason = 'low_confidence'
                    else:
                        # One sustained wrist change OR two supporting body joints.
                        wrists = [(common[j]/.10, j) for j in (9, 10) if j in common]
                        body = sorted([(v/.06, j) for j, v in common.items()
                                       if j not in (9, 10)], reverse=True)
                        choices = wrists + (body[1:2] if len(body) >= 2 else [])
                        if choices:
                            score, joint = max(choices)
                            status, reason = ('suspect', 'motion') if score >= 1 else ('still', 'below_threshold')
                            if score < 1 and any(j not in common for j in (7, 8, 9, 10)):
                                status, reason = 'hold', 'partial_pose'
                state['seen'] = now
            if state:
                if status == 'suspect':
                    if state['suspect'] is None:
                        state['suspect'], state['count'] = now, 0
                    state['count'] += 1
                    if now-state['suspect'] >= .2 and state['count'] >= 3 and not state['failed']:
                        state['failed'] = True
                        self.events.append(dict(track_id=tid, kind='pose_stop_motion_candidate',
                            after_stop_s=round(now-command['requested_at'], 2),
                            score=round(score, 3), joint=joint))
                else:
                    state['suspect'], state['count'] = None, 0
            output.append(dict(track_id=tid, status=status, reason=reason,
                score=None if score is None else round(score, 3), joint=joint,
                valid_joints=len(common), visible_joints=len(points),
                stop_baseline_ready=bool(state and state['anchor']),
                stop_candidate=bool(state and state['failed'])))
        return dict(method='pose_fixed_baseline', phase=self.phase, version=command['version'],
            observations=output, events=list(self.events),
            missing_ids=[tid for tid, s in self.states.items() if now-s['seen'] > .5],
            parameters=dict(confidence=.5, wrist_displacement=.10, body_displacement=.06,
                body_support=2, min_joints=4, min_torso=2, confirmation_s=.2,
                confirmation_samples=3, max_gap_s=.5, grace_s=0),
            note='Local trial only; score >= 1 must persist. No identity reassociation.')
