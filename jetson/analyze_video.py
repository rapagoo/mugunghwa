"""Save full-clip detection/ROI evidence; does not send events to PI or judge players."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time

os.environ['YOLO_AUTOINSTALL'] = 'false'
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from game import geometry
from game.source import FrameSource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True, help='ignored data or .runtime directory')
    parser.add_argument('--imgsz', type=int, default=320)
    parser.add_argument('--model', default=str(Path(__file__).parent / 'examples/yolov8n.pt'))
    args = parser.parse_args()
    if args.imgsz <= 0 or not Path(args.model).is_file():
        parser.error('Positive image size and an existing model file are required')
    config = geometry.load(args.config)
    capture = FrameSource(video=args.video)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    writer = None
    counts, roi_counts = Counter(), Counter()
    tracks = {}
    frames = 0
    started = time.monotonic()
    try:
        first = capture.read()
        if first is None:
            raise RuntimeError('Empty video')
        height, width = first[0].shape[:2]
        geometry.check_size(config, width, height)
        print('VIDEO_META', json.dumps(dict(width=width, height=height, fps=capture.fps)), flush=True)
        # Capture evidence before initializing the detector, for calibration review.
        cv2.imwrite(str(output / 'calibration-first.jpg'), geometry.overlay(first[0].copy(), config))
        model = YOLO(args.model)
        options = dict(imgsz=args.imgsz, classes=[0], conf=0.35, device=0 if torch.cuda.is_available() else 'cpu',
                       persist=True, tracker='bytetrack.yaml', verbose=False)
        model.track(np.zeros((height, width, 3), dtype=np.uint8), **options)
        preview_width = 960
        preview_height = round(height * preview_width / width / 2) * 2
        writer = cv2.VideoWriter(str(output / 'annotated.mp4'), cv2.VideoWriter_fourcc(*'mp4v'),
                                 capture.fps, (preview_width, preview_height))
        if not writer.isOpened():
            raise RuntimeError('Cannot open annotated video writer')
        item = first
        with (output / 'frames.jsonl').open('w', encoding='utf-8') as evidence:
            while item is not None:
                frame, timestamp, _ = item
                result = model.track(frame, **options)[0]
                boxes = result.boxes
                ids = [] if boxes.id is None else boxes.id.int().cpu().tolist()
                detections = []
                preview = geometry.overlay(cv2.resize(frame, (preview_width, preview_height)), config)
                for i, (x1, y1, x2, y2) in enumerate(boxes.xyxy.cpu().tolist()):
                    foot = [(x1 + x2) / 2 / width, y2 / height]
                    included = geometry.inside(foot, config['roi'])
                    track = ids[i] if i < len(ids) else None
                    detections.append(dict(track_id=track, foot=foot, in_roi=included,
                                           box=[x1 / width, y1 / height, x2 / width, y2 / height],
                                           confidence=float(boxes.conf[i].item())))
                    color = (80, 230, 100) if included else (170, 170, 170)
                    a = (round(x1 / width * preview_width), round(y1 / height * preview_height))
                    b = (round(x2 / width * preview_width), round(y2 / height * preview_height))
                    cv2.rectangle(preview, a, b, color, 2)
                    cv2.circle(preview, (round(foot[0] * preview_width), round(foot[1] * preview_height)), 5, color, -1)
                    cv2.putText(preview, 'ID {} {}'.format(track, 'IN' if included else 'OUT'),
                                (a[0], max(20, a[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2)
                    if track is not None:
                        stat = tracks.setdefault(str(track), dict(first_s=timestamp, last_s=timestamp, frames=0, roi_frames=0))
                        stat['last_s'] = timestamp
                        stat['frames'] += 1
                        stat['roi_frames'] += int(included)
                roi_count = sum(d['in_roi'] for d in detections)
                counts[len(detections)] += 1
                roi_counts[roi_count] += 1
                frames += 1
                cv2.putText(preview, '{:.2f}s | detected {} | ROI {}'.format(timestamp, len(detections), roi_count),
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
                writer.write(preview)
                if frames == 1 or frames % max(1, round(capture.fps * 5)) == 0:
                    cv2.imwrite(str(output / 'frame-{:05d}.jpg'.format(frames)), preview)
                if frames == 1 or frames % max(1, round(capture.fps)) == 0:
                    print('PROGRESS frames={} media_s={:.2f} people={} roi={}'.format(frames, timestamp, len(detections), roi_count), flush=True)
                evidence.write(json.dumps(dict(frame=frames, media_s=timestamp, detections=detections)) + '\n')
                item = capture.read()
        report = dict(video=Path(args.video).name, frames=frames, fps=capture.fps,
                      last_media_s=timestamp, width=width, height=height, imgsz=args.imgsz,
                      detections_per_frame=dict(counts), roi_people_per_frame=dict(roi_counts),
                      provisional_tracks=tracks, elapsed_s=time.monotonic() - started,
                      note='Detection/ROI evidence only. No finish/motion/elimination verdicts.')
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('VIDEO_ANALYSIS_DONE', json.dumps(report), flush=True)
    finally:
        if writer:
            writer.release()
        capture.close()


if __name__ == '__main__':
    main()
