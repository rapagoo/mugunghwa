"""Headless webcam/video detector with a read-only LAN dashboard."""
import argparse
import os
from pathlib import Path
import threading
import time

os.environ['YOLO_AUTOINSTALL'] = 'false'
from game.web import Monitor, GameDatabase, create_server
from game.realtime import LatestFrame


def run_vision(args, monitor, stop):
    # Heavy dependencies stay outside HTTP threads and database tests.
    import cv2
    import torch
    from game.source import FrameSource
    from game.detector import load_detector
    from game import geometry
    from game.finish import FinishDetector
    slot = LatestFrame()
    capture = None
    reader = None
    try:
        config = geometry.load(args.config) if args.config else None
        capture = FrameSource(camera=args.camera, video=args.video)
        first = capture.read()
        if first is None:
            raise ValueError('Empty source')
        if config:
            geometry.check_size(config, first[0].shape[1], first[0].shape[0])
        model, size = load_detector(args.model, args.imgsz)
        options = dict(imgsz=size, conf=.35, classes=[0], persist=True,
                       tracker='bytetrack.yaml', verbose=False,
                       device=0 if torch.cuda.is_available() else 'cpu')
        for _ in range(5):
            model.track(first[0], **options)

        def read_frames():
            try:
                packet = first
                anchor = time.monotonic()
                while not stop.is_set():
                    if packet is None:
                        if not args.loop or not args.video:
                            slot.close()
                            break
                        capture.restart()
                        packet = capture.read()
                        anchor = time.monotonic()
                        if packet is None:
                            raise ValueError('Cannot restart source')
                    frame, media, epoch = packet
                    if args.video and stop.wait(max(0, anchor + media - time.monotonic())):
                        break
                    slot.publish((frame, media, epoch, time.monotonic()))
                    packet = capture.read()
            except Exception as error:
                monitor.update(dict(state='error', error=str(error)))
                slot.close()

        reader = threading.Thread(target=read_frames, daemon=True, name='capture')
        reader.start()
        serial, epoch, previous, last_jpeg = 0, None, None, 0
        finish = None
        while not stop.is_set():
            packet = slot.next(serial)
            if packet is None:
                if monitor.snapshot()['state'] != 'error':
                    monitor.update(dict(state='ended'))
                break
            serial, (frame, media, current_epoch, source_wall) = packet
            if current_epoch != epoch:
                for tracker in model.predictor.trackers:
                    tracker.reset()
                epoch, previous = current_epoch, None
                finish = FinishDetector(config) if config else None
            start = time.monotonic()
            result = model.track(frame, **options)[0]
            boxes = result.boxes.xyxy.cpu().tolist()
            ids = [] if result.boxes.id is None else result.boxes.id.int().cpu().tolist()
            height, width = frame.shape[:2]
            if finish:
                for tid, (x1,y1,x2,y2) in zip(ids, boxes):
                    finish.update(tid, [(x1+x2)/2/width,y2/height], media)
            completed = time.monotonic()
            data = dict(state='running', epoch=epoch, media_s=media, people=len(boxes),
                        track_ids=ids, candidates=list(finish.completed.values()) if finish else [],
                        processing_ms=round((completed-start)*1000, 1),
                        interval_ms=None if previous is None else round((completed-previous)*1000,1),
                        result_latency_ms=round((completed-source_wall)*1000,1),
                        completed_wall=completed, preview_hz=args.preview_hz,
                        width=width, height=height, source_fps=capture.fps)
            jpeg = None
            if completed-last_jpeg >= 1/args.preview_hz:
                preview = frame.copy()
                if config:
                    geometry.overlay(preview, config)
                for i, (x1,y1,x2,y2) in enumerate(boxes):
                    cv2.rectangle(preview,(round(x1),round(y1)),(round(x2),round(y2)),(0,220,255),2)
                    cv2.putText(preview,'Track {}'.format(ids[i] if i < len(ids) else '?'),
                                (round(x1),max(20,round(y1)-5)),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,220,255),2)
                if width > 960:
                    preview = cv2.resize(preview,(960,round(height*960/width)))
                ok, encoded = cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,75])
                if not ok:
                    raise RuntimeError('JPEG encoding failed')
                jpeg = encoded.tobytes()
                last_jpeg = completed
            monitor.update(data, jpeg)
            previous = completed
    except Exception as error:
        monitor.update(dict(state='error', error=str(error)))
    finally:
        stop.set()
        slot.close()
        if reader:
            reader.join(3)
        if capture and (reader is None or not reader.is_alive()):
            capture.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--video')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--config')
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--model', default=str(Path(__file__).parent/'examples/yolov8n.pt'))
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--preview-hz', type=float, default=5)
    parser.add_argument('--database', default='.runtime/web/game.db')
    args = parser.parse_args()
    if not 0 < args.preview_hz <= 15 or args.imgsz <= 0:
        parser.error('preview-hz must be >0 and <=15; imgsz must be positive')
    monitor = Monitor('video' if args.video else 'camera')
    database = GameDatabase(args.database)
    server = create_server(args.host,args.port,monitor,database)
    stop = threading.Event()
    worker = threading.Thread(target=run_vision,args=(args,monitor,stop),daemon=True)
    worker.start()
    print('Monitor listening on {}:{}'.format(*server.server_address),flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        monitor.close()
        server.server_close()
        worker.join(5)


if __name__ == '__main__':
    main()
