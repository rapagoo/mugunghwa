"""Translate fresh cached observations into phase-bound Pi game reports."""


def enroll(state):
    if not state.get('calibrated'):
        raise ValueError('Calibration required')
    ids = sorted({o['track_id'] for o in state.get('validation',{}).get('observations',[])
                  if o.get('in_roi') and isinstance(o.get('track_id'),int) and o['track_id']>0})
    if len(ids)>32:
        raise ValueError('At most 32 participants supported')
    return ids


def observations(state, expected):
    if not expected:
        return []
    trial = state.get('pose_trial',{})
    if trial.get('phase')!=expected['phase'] or trial.get('version')!=expected['version']:
        return []
    verdicts = {}
    for candidate in state.get('candidates',[]):
        if candidate.get('phase_version')==expected['version'] and candidate.get('phase')==expected['phase']:
            if expected['phase'] in ('move','stop'):
                verdicts[candidate['track_id']]='PASS' if expected['phase']=='move' else 'FAIL'
    if expected['phase']=='stop':
        for person in trial.get('observations',[]):
            if person.get('stop_candidate'):
                verdicts[person['track_id']]='FAIL'
    return sorted(verdicts.items())
