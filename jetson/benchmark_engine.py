"""Offline like-for-like engine timing and detection evidence; no PI/MCU traffic."""
import argparse
from collections import Counter
import json
from pathlib import Path
import os
import time
import statistics

os.environ['YOLO_AUTOINSTALL'] = 'false'
import numpy as np
import torch
from game.detector import load_detector, pose_keypoints
from game.source import FrameSource
from game import geometry
from game.finish import FinishDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--video')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--config')
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--frames', type=int)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    if not args.video and not args.frames:
        parser.error('webcam benchmark requires --frames')
    if args.frames is not None and args.frames <= 0:
        parser.error('positive frame count required')
    config = geometry.load(args.config) if args.config else None
    detector = FinishDetector(config) if config else None
    model, size = load_detector(args.model, args.imgsz)
    options = dict(imgsz=size, conf=.35, classes=[0], device=0, persist=True, tracker='bytetrack.yaml', verbose=False)
    cap = FrameSource(args.camera, args.video)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = detected = roi_frames = tracked = 0
    ids_count = Counter()
    timings, inference, events = [], [], []
    people_counts, visible_keypoints = [], []
    try:
        first = cap.read()
        if first is None:
            raise RuntimeError('No frame')
        h, w = first[0].shape[:2]
        if config:
            geometry.check_size(config, w, h)
        for _ in range(5):
            model.track(first[0], **options)
        actual_shape = list(model.predictor.preprocess([first[0]]).shape)
        for tracker in model.predictor.trackers:
            tracker.reset()
        if args.video:
            cap.restart()
        print('BENCHMARK_READY', json.dumps(dict(model=args.model, tensor_shape=actual_shape, source=[w,h])), flush=True)
        with path.with_suffix('.frames.jsonl').open('w') as evidence:
            while args.frames is None or frames < args.frames:
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                item = cap.read()
                t1 = time.perf_counter()
                if item is None:
                    break
                frame, media, _ = item
                result = model.track(frame, **options)[0]
                torch.cuda.synchronize()
                t2 = time.perf_counter()
                boxes = result.boxes.xyxy.cpu().tolist()
                keypoints = pose_keypoints(result,boxes)
                if keypoints is not None:
                    visible_keypoints.extend(sum(k[2]>=.5 for k in person) for person in keypoints)
                people_counts.append(len(boxes))
                ids = [] if result.boxes.id is None else result.boxes.id.int().cpu().tolist()
                feet = [[(x1+x2)/2/w,y2/h] for x1,y1,x2,y2 in boxes]
                included = [geometry.inside(p,config['roi']) for p in feet] if config else [True]*len(feet)
                for tid, foot in zip(ids,feet):
                    ids_count[tid] += 1
                    event = detector.update(tid,foot,media) if detector else None
                    if event:
                        events.append(event)
                t3 = time.perf_counter()
                timings.append([(t1-t0)*1000,(t2-t1)*1000,(t3-t2)*1000,(t3-t0)*1000])
                inference.append(result.speed['inference'])
                frames += 1
                detected += int(bool(boxes))
                tracked += int(bool(ids))
                roi_frames += int(any(included))
                # Evidence serialization is excluded from the measured processing times.
                evidence.write(json.dumps(dict(frame=frames,media_s=media,boxes=boxes,ids=ids,feet=feet,keypoints=keypoints))+'\n')
                if frames % 120 == 0:
                    print('PROGRESS',frames,round(1000/statistics.mean(t[3] for t in timings),2),flush=True)
        report = dict(model=args.model,source=args.video or 'webcam',source_size=[w,h],tensor_shape=actual_shape,
                      frames=frames,processing_fps=1000/statistics.mean(t[3] for t in timings),
                      mean_ms=dict(zip(['capture','track_call','geometry','total'],np.mean(timings,axis=0).tolist())),
                      total_p95_ms=float(np.percentile([t[3] for t in timings],95)),
                      inference_mean_ms=statistics.mean(inference),inference_p95_ms=float(np.percentile(inference,95)),
                      detected_frames=detected,tracked_frames=tracked,roi_frames=roi_frames,
                      people_min=min(people_counts),people_max=max(people_counts),
                      keypoint_confidence_threshold=.5,
                      mean_visible_keypoints=statistics.mean(visible_keypoints) if visible_keypoints else None,
                      ids=dict(ids_count),finish_candidates=events,
                      note='Warmup excluded; no GUI/file-output timing or network. Detection presence is not ground-truth accuracy.')
        path.write_text(json.dumps(report,indent=2))
        print('RESULT',json.dumps(report),flush=True)
    finally:
        cap.close()


if __name__ == '__main__':
    main()
