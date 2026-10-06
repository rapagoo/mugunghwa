"""Offline video at media speed, with asynchronous latest-frame person detection."""
import argparse
import json
import os
from pathlib import Path
import threading
import time
import statistics

os.environ['YOLO_AUTOINSTALL'] = 'false'
import cv2
import torch
from game.source import FrameSource
from game import geometry
from game.finish import FinishDetector
from game.realtime import LatestFrame, ReplayClock
from game.detector import load_detector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--model', default=str(Path(__file__).parent / 'examples/yolov8n.pt'))
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--cycles', type=int, help='stop after this many repetitions; requires --loop')
    parser.add_argument('--metrics', help='optional JSONL detection and replay timing log')
    args = parser.parse_args()
    if args.imgsz <= 0 or not Path(args.model).is_file():
        parser.error('positive image size and existing model required')
    if args.cycles is not None and (args.cycles <= 0 or not args.loop):
        parser.error('positive --cycles requires --loop')
    config = geometry.load(args.config)
    capture = FrameSource(video=args.video)
    first = capture.read()
    if first is None:
        capture.close()
        raise RuntimeError('Empty video')
    geometry.check_size(config, first[0].shape[1], first[0].shape[0])
    window = 'Mugunghwa - realtime replay'
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 960, 540)
    initial = cv2.resize(first[0], (960, 540))
    cv2.putText(initial, 'Preparing detector; replay starts after warmup', (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
    cv2.imshow(window, initial)
    cv2.waitKey(1)
    # The first frame may contain no detections, so also warm on a later frame
    # before starting the media clock (covers postprocessing/track initialization).
    capture.cap.set(cv2.CAP_PROP_POS_MSEC, 2000)
    sample = capture.read()
    warm_frame = first[0] if sample is None else sample[0]
    capture.restart()
    first = capture.read()
    if first is None:
        capture.close()
        cv2.destroyAllWindows()
        raise RuntimeError('Cannot restart video for replay')
    slot = LatestFrame()
    ready = threading.Event()
    result_lock = threading.Lock()
    shared = dict(result=None, error=None)
    log = None
    if args.metrics:
        path = Path(args.metrics)
        path.parent.mkdir(parents=True, exist_ok=True)
        log = path.open('w', encoding='utf-8')
    log_lock = threading.Lock()

    def record(data):
        print(json.dumps(data), flush=True)
        if log:
            with log_lock:
                log.write(json.dumps(data) + '\n')
                log.flush()

    def worker():
        try:
            model, input_size = load_detector(args.model, args.imgsz)
            options = dict(imgsz=input_size, conf=.35, classes=[0], device=0 if torch.cuda.is_available() else 'cpu',
                           persist=True, tracker='bytetrack.yaml', verbose=False)
            for _ in range(5):
                model.track(warm_frame, **options)
            serial, epoch, last_completed, last_media = 0, None, None, None
            finish = None
            ready.set()
            while True:
                packet = slot.next(serial)
                if packet is None:
                    break
                serial, (frame, media, current_epoch, frame_wall) = packet
                if epoch != current_epoch:
                    for tracker in model.predictor.trackers:
                        tracker.reset()
                    epoch = current_epoch
                    finish = FinishDetector(config)
                    last_completed = last_media = None
                start = time.monotonic()
                result = model.track(frame, **options)[0]
                coordinates = result.boxes.xyxy.cpu().tolist()
                ids = [] if result.boxes.id is None else result.boxes.id.int().cpu().tolist()
                height, width = frame.shape[:2]
                events = []
                for tid, (x1, y1, x2, y2) in zip(ids, coordinates):
                    event = finish.update(tid, [(x1+x2)/2/width, y2/height], media)
                    if event:
                        events.append(event)
                completed = time.monotonic()
                data = dict(kind='detection', epoch=epoch, media_s=media,
                            completed_wall_s=completed, source_wall_s=frame_wall,
                            interval_ms=None if last_completed is None else (completed-last_completed)*1000,
                            sample_gap_ms=None if last_media is None else (media-last_media)*1000,
                            processing_ms=(completed-start)*1000,
                            result_latency_ms=(completed-frame_wall)*1000,
                            people=len(coordinates), ids=ids, finish_candidates=events)
                with result_lock:
                    shared['result'] = dict(data=data, boxes=coordinates, ids=ids,
                                            candidates=list(finish.completed.values()))
                record(data)
                last_completed, last_media = completed, media
        except Exception as error:
            with result_lock:
                shared['error'] = repr(error)
            ready.set()

    thread = threading.Thread(target=worker, name='person-detector', daemon=True)
    thread.start()
    try:
        while not ready.wait(.02):
            if cv2.waitKey(1) & 0xff == ord('q'):
                return
        epoch, shown, skipped = 0, 0, 0
        clock = ReplayClock(time.monotonic())
        cycle_start = time.monotonic()
        pending = first
        last_frame = None
        intervals = []
        last_serial_media = None
        late_max = 0
        while True:
            selected = None
            with result_lock:
                latest = shared['result']
                error = shared['error']
            if error:
                raise RuntimeError(error)
            now = time.monotonic()
            target = clock.media(now)
            if clock.paused_at is None:
                # Decode at source speed; if GUI falls behind, skip expired display frames.
                while pending is not None and pending[1] <= target:
                    if selected is not None:
                        skipped += 1
                    selected = pending
                    pending = capture.read()
                if selected is not None:
                    frame, media, _ = selected
                    last_frame = (frame, media)
                    slot.publish((frame, media, epoch, time.monotonic()))
                    shown += 1
                    late_max = max(late_max, max(0, target-media))
            if last_frame is not None and (selected is not None or clock.paused_at is not None):
                frame, media = last_frame
                preview = frame.copy()
                geometry.overlay(preview, config)
                valid = latest is not None and latest['data']['epoch'] == epoch
                if valid:
                    data = latest['data']
                    age = max(0, media-data['media_s'])*1000
                    key = (epoch, data['media_s'])
                    if key != last_serial_media:
                        if data['interval_ms'] is not None:
                            intervals.append(data['interval_ms'])
                        last_serial_media = key
                    if age < 500:
                        for i, (x1,y1,x2,y2) in enumerate(latest['boxes']):
                            cv2.rectangle(preview, (round(x1),round(y1)), (round(x2),round(y2)), (0,220,255), 2)
                            tid = latest['ids'][i] if i < len(latest['ids']) else '?'
                            cv2.putText(preview, 'ID {} (previous detection)'.format(tid),
                                        (round(x1),max(25,round(y1)-5)), cv2.FONT_HERSHEY_SIMPLEX, .5, (0,220,255), 1)
                    text = 'detect interval {} ms | processing {:.0f} ms | box age {:.0f} ms'.format(
                        '--' if data['interval_ms'] is None else round(data['interval_ms']), data['processing_ms'], age)
                    cv2.putText(preview, text, (10,52), cv2.FONT_HERSHEY_SIMPLEX, .55, (0,255,255), 2)
                    if latest['candidates']:
                        event = latest['candidates'][-1]
                        cv2.putText(preview, 'FINISH CANDIDATE ID {} @ {:.2f}s'.format(event['track_id'],event['crossed_at']),
                                    (10,78),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,255),2)
                display_fps = shown/max(.001,time.monotonic()-cycle_start)
                cv2.putText(preview, '1x | {:.2f}s | source {:.1f}fps | display {:.1f}fps | {}'.format(
                    media,capture.fps,display_fps,'PAUSED' if clock.paused_at is not None else 'PLAYING'),
                    (10,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
                cv2.imshow(window,preview)
                if clock.paused_at is None:
                    late_max = max(late_max,max(0,clock.media(time.monotonic())-media))
            wait_ms = 10 if pending is None or clock.paused_at is not None else max(
                1, min(10, round((pending[1]-clock.media(time.monotonic()))*1000)))
            key = cv2.waitKey(wait_ms) & 0xff
            if key == ord('q') or cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord(' '):
                clock.toggle(time.monotonic())
            ended = pending is None and target >= capture.index/capture.fps
            if key == ord('r') or (ended and args.loop):
                record(dict(kind='replay',epoch=epoch,shown=shown,skipped_display_frames=skipped,
                            wall_s=time.monotonic()-cycle_start,
                            mean_detect_interval_ms=statistics.mean(intervals) if intervals else None,
                            max_display_lateness_ms=late_max*1000))
                if ended and args.cycles is not None and epoch + 1 >= args.cycles:
                    break
                capture.restart()
                pending = capture.read()
                epoch += 1
                clock = ReplayClock(time.monotonic())
                cycle_start = time.monotonic()
                shown = skipped = 0
                late_max = 0
                intervals=[]
                last_frame = None
            elif ended:
                break
    finally:
        slot.close()
        thread.join(10)
        capture.close()
        cv2.destroyAllWindows()
        # Worker can still be completing a CUDA call during an interrupted warmup.
        if log and not thread.is_alive():
            log.close()


if __name__ == '__main__':
    main()
