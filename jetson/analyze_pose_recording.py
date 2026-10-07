"""Analyze private recorded coordinates; distinguish motion from accuracy/jitter claims."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def percentile(values, fraction):
    return round(sorted(values)[min(len(values)-1,int((len(values)-1)*fraction))],3) if values else None


def analyze(folder):
    folder=Path(folder)
    metadata=json.loads((folder/'metadata.json').read_text())
    records=[json.loads(line) for line in (folder/'samples.jsonl').read_text().splitlines() if line]
    counts=Counter();visible=[];steps=[];previous={};joints={};gaps=[]
    for record in records:
        now=record['source_wall']
        points=record.get('keypoints') or []
        visible.extend(sum(k[2]>=.5 for k in person) for person in points)
        for i,tid in enumerate(record['ids']):
            counts[tid]+=1
            if i>=len(points): continue
            person=points[i]
            box=record['boxes'][i];scale=max(box[3]-box[1],1)
            old=previous.get(tid)
            if old:
                gap=now-old[0]
                if gap>.5: gaps.append(dict(track_id=tid,gap_s=round(gap,3)))
                elif gap>0:
                    for k,(a,b) in enumerate(zip(old[1],person)):
                        if a[2]>=.5 and b[2]>=.5:
                            delta=math.dist(a[:2],b[:2])/scale
                            steps.append(delta);joints.setdefault(k,[]).append(delta)
            previous[tid]=(now,person)
    intervals=[r['interval_ms'] for r in records if r.get('interval_ms') is not None]
    report=dict(session_id=folder.name,scenario=metadata['scenario'],saved_samples=len(records),
        no_person_samples=sum(not r['boxes'] for r in records),id_observation_counts=dict(counts),
        untracked_person_observations=sum(len(r['boxes'])-len(r['ids']) for r in records),
        mean_interval_ms=round(statistics.mean(intervals),3) if intervals else None,
        interval_p95_ms=percentile(intervals,.95),
        mean_visible_keypoints=round(statistics.mean(visible),3) if visible else None,
        adjacent_joint_displacement_p95_body_heights=percentile(steps,.95),
        per_joint_displacement_p95={k:percentile(v,.95) for k,v in joints.items()},
        same_id_gaps=gaps,
        note='Displacement is actual motion plus estimation noise, not ground-truth error. Compare saved JPEGs; only a still trial can suggest jitter.')
    (folder/'analysis.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    (folder/'analysis.json').chmod(0o600)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    args=parser.parse_args()
    print(json.dumps(analyze(args.folder),indent=2,ensure_ascii=False))
