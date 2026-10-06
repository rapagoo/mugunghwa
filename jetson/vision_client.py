"""Live person observations to PI; track IDs are provisional, not participant IDs."""
import argparse
import os
from pathlib import Path
import socket
import time
import uuid
from contextlib import ExitStack

# Never let Ultralytics install or upgrade dependencies during a camera run.
os.environ['YOLO_AUTOINSTALL'] = 'false'
import cv2
import numpy as np
import torch
from game.source import FrameSource
from game import geometry
from game.finish import FinishDetector
from game.detector import load_detector


def receive_line(stream):
    line = stream.readline(101)
    if not line or not line.endswith(b'\n') or len(line) > 100:
        raise RuntimeError('PI disconnected or returned an invalid line')
    return line.decode('ascii').strip()


def normalized(value, extent):
    return max(0, min(1000, round(float(value) * 1000 / extent)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='10.10.16.90')
    parser.add_argument('--port', type=int, default=5000)
    source_args = parser.add_mutually_exclusive_group()
    source_args.add_argument('--camera', type=int, default=0)
    source_args.add_argument('--video', help='recorded video; currently offline only')
    parser.add_argument('--offline', action='store_true', help='inspect without connecting to PI')
    parser.add_argument('--config', help='calibration JSON exported by game/calibrate.html')
    parser.add_argument('--loop', action='store_true', help='repeat video with fresh tracker state')
    parser.add_argument('--speed', type=float, default=1, help='video replay speed, 0.1..4')
    parser.add_argument('--preview-output', help='write the latest annotated frame to this image path')
    parser.add_argument('--pause-on-candidate', action='store_true', help='pause video when a finish candidate is confirmed')
    parser.add_argument('--model', default=str(Path(__file__).parent / 'examples/yolov8n.pt'))
    parser.add_argument('--imgsz', type=int, default=320)
    parser.add_argument('--conf', type=float, default=0.35)
    parser.add_argument('--send-hz', type=float, default=2)
    parser.add_argument('--frames', type=int, help='stop after this many processed frames')
    parser.add_argument('--display', action='store_true', help='requires Jetson desktop display')
    args = parser.parse_args()
    if (not 1 <= args.port <= 65535 or args.imgsz <= 0 or not 0 < args.conf < 1
            or not 0 < args.send_hz <= 10 or not 0.1 <= args.speed <= 4
            or (args.frames is not None and args.frames <= 0)):
        parser.error('invalid port, image size, confidence, send rate or frame limit')
    if not Path(args.model).is_file():
        parser.error('model file does not exist: ' + args.model)
    if args.video and not args.offline:
        parser.error('Use --offline for video replay; PI game/media clock sync is not implemented yet')
    if args.video and not Path(args.video).is_file():
        parser.error('video file does not exist: ' + args.video)
    if args.loop and not args.video:
        parser.error('--loop requires --video')
    calibration = geometry.load(args.config) if args.config else None
    if args.pause_on_candidate and not (args.video and args.display and calibration):
        parser.error('--pause-on-candidate requires video, display and config')
    finish = FinishDetector(calibration) if calibration else None
    window = 'Mugunghwa - provisional tracks'
    if args.display:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 960, 540)
        preparing = np.zeros((540, 960, 3), dtype=np.uint8)
        cv2.putText(preparing, 'Preparing detector... Please wait', (60, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.imshow(window, preparing)
        cv2.waitKey(1)

    device = 0 if torch.cuda.is_available() else 'cpu'
    model, input_size = load_detector(args.model, args.imgsz)
    options = dict(imgsz=input_size, conf=args.conf, classes=[0], device=device,
                   tracker='bytetrack.yaml', persist=True, verbose=False)
    print('WARMUP device=', device, flush=True)
    model.track(np.zeros((480, 640, 3), dtype=np.uint8), **options)
    boot = uuid.uuid4().hex[:8]
    capture = FrameSource(args.camera, args.video, args.loop)
    try:
        with ExitStack() as resources:
            conn = stream = None
            if not args.offline:
                conn = resources.enter_context(socket.create_connection((args.host, args.port), timeout=5))
                conn.settimeout(3)
                stream = resources.enter_context(conn.makefile('rb'))
                conn.sendall(b'[JETSON:PASSWD]')
                reply = receive_line(stream)
                if not reply.startswith('[JETSON] New connected!'):
                    raise RuntimeError('JETSON login rejected: ' + reply)
            print('VISION_READY boot=' + boot + (' OFFLINE' if args.offline else ''), flush=True)
            last_sent = float('-inf')
            seq, epoch, paused = 0, 0, False
            while args.frames is None or seq < args.frames:
                if paused:
                    key = cv2.waitKey(40) & 0xff
                    if key == ord('q'):
                        break
                    if key == ord('r') and capture.restart():
                        paused = False
                    if key not in (ord(' '), ord('n')) and paused:
                        continue
                    if key == ord(' '):
                        paused = False
                start = time.monotonic()
                item = capture.read()
                if item is None:
                    print('VIDEO_END', flush=True)
                    break
                frame, media_seconds, current_epoch = item
                if current_epoch != epoch:
                    for tracker in getattr(model.predictor, 'trackers', []):
                        tracker.reset()
                    epoch = current_epoch
                    finish = FinishDetector(calibration) if calibration else None
                    print('REPLAY_RESET epoch=' + str(epoch), flush=True)
                seq += 1
                if seq > 2147483647:
                    raise RuntimeError('Frame sequence exhausted; restart with a new boot ID')
                height, width = frame.shape[:2]
                if calibration:
                    geometry.check_size(calibration, width, height)
                result = model.track(frame, **options)[0]
                boxes = result.boxes
                coordinates = boxes.xyxy.cpu().tolist()
                ids = [] if boxes.id is None else boxes.id.int().cpu().tolist()
                included = [i for i, (x1, y1, x2, y2) in enumerate(coordinates)
                            if not calibration or geometry.inside(
                                ((x1 + x2) / 2 / width, y2 / height), calibration['roi'])]
                tracks = [(ids[i], coordinates[i]) for i in included if i < len(ids)]
                new_events = []
                if finish:
                    for track_id, (x1, y1, x2, y2) in zip(ids, coordinates):
                        event = finish.update(track_id, [(x1 + x2) / 2 / width, y2 / height], media_seconds)
                        if event:
                            new_events.append(event)
                            print('FINISH_CANDIDATE epoch={} track={} crossed_s={:.3f} confirmed_s={:.3f}'.format(
                                epoch, track_id, event['crossed_at'], event['confirmed_at']), flush=True)
                people = len(included)
                now = time.monotonic()
                if now - last_sent >= 1 / args.send_hz:
                    messages = []
                    for track_id, (x1, y1, x2, y2) in tracks:
                        if not 1 <= track_id <= 2147483647:
                            raise RuntimeError('Track ID outside protocol range')
                        messages.append('[PI]POSITION@{}@{}@{}@{}@{}\n'.format(
                            boot, seq, track_id, normalized((x1 + x2) / 2, width), normalized(y2, height)))
                    messages.append('[PI]VISION@{}@{}@{}@{}\n'.format(boot, seq, people, len(tracks)))
                    if people > 999:
                        raise RuntimeError('Observation count outside protocol range')
                    if conn:
                        conn.sendall(''.join(messages).encode('ascii'))
                        ack = receive_line(stream)
                        if ack != '[PI]VISION_ACK@{}@{}'.format(boot, seq):
                            raise RuntimeError('Unexpected observation reply: ' + ack)
                    last_sent = now
                    print('VISION seq={} media_s={:.3f} epoch={} people={} tracked={} inference_ms={:.1f} {}'.format(
                        seq, media_seconds, epoch, people, len(tracks), (now - start) * 1000,
                        'OFFLINE' if args.offline else 'ACK'), flush=True)
                if args.display or args.preview_output:
                    preview = result.plot()
                    if calibration:
                        geometry.overlay(preview, calibration)
                    cv2.putText(preview, 'media {:.2f}s | ROI {} | epoch {}'.format(media_seconds, people, epoch),
                                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                    if finish and finish.completed:
                        latest = max(finish.completed.values(), key=lambda e: e['confirmed_at'])
                        cv2.putText(preview, 'FINISH CANDIDATE ID {} @ {:.2f}s | total {}'.format(
                            latest['track_id'], latest['crossed_at'], len(finish.completed)),
                            (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
                    if args.preview_output:
                        output = Path(args.preview_output)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        if not cv2.imwrite(str(output), preview):
                            raise RuntimeError('Cannot write preview')
                    if args.display:
                        cv2.imshow(window, preview)
                        key = cv2.waitKey(1) & 0xff
                        if key == ord('q'):
                            break
                        if args.video:
                            if new_events and args.pause_on_candidate:
                                paused = True
                            if key == ord(' '):
                                paused = True
                            if key == ord('r'):
                                capture.restart()
                if args.video and not paused:
                    time.sleep(max(0, 1 / capture.fps / args.speed - (time.monotonic() - start)))
    finally:
        capture.close()
        if args.display:
            cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped', flush=True)
