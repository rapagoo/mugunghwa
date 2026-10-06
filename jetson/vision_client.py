"""Live person observations to PI; track IDs are provisional, not participant IDs."""
import argparse
import os
from pathlib import Path
import socket
import time
import uuid

# Never let Ultralytics install or upgrade dependencies during a camera run.
os.environ['YOLO_AUTOINSTALL'] = 'false'
import cv2
import numpy as np
import torch
from ultralytics import YOLO


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
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--model', default=str(Path(__file__).parent / 'examples/yolov8n.pt'))
    parser.add_argument('--imgsz', type=int, default=320)
    parser.add_argument('--conf', type=float, default=0.35)
    parser.add_argument('--send-hz', type=float, default=2)
    parser.add_argument('--frames', type=int, help='stop after this many processed frames')
    parser.add_argument('--display', action='store_true', help='requires Jetson desktop display')
    args = parser.parse_args()
    if (not 1 <= args.port <= 65535 or args.imgsz <= 0 or not 0 < args.conf < 1
            or not 0 < args.send_hz <= 10 or (args.frames is not None and args.frames <= 0)):
        parser.error('invalid port, image size, confidence, send rate or frame limit')
    if not Path(args.model).is_file():
        parser.error('model file does not exist: ' + args.model)

    device = 0 if torch.cuda.is_available() else 'cpu'
    model = YOLO(args.model)
    options = dict(imgsz=args.imgsz, conf=args.conf, classes=[0], device=device,
                   tracker='bytetrack.yaml', persist=True, verbose=False)
    print('WARMUP device=', device, flush=True)
    model.track(np.zeros((480, 640, 3), dtype=np.uint8), **options)
    boot = uuid.uuid4().hex[:8]
    cap = cv2.VideoCapture(args.camera)
    try:
        if not cap.isOpened():
            raise RuntimeError('Cannot open webcam')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        with socket.create_connection((args.host, args.port), timeout=5) as conn:
            conn.settimeout(3)
            with conn.makefile('rb') as stream:
                conn.sendall(b'[JETSON:PASSWD]')
                reply = receive_line(stream)
                if not reply.startswith('[JETSON] New connected!'):
                    raise RuntimeError('JETSON login rejected: ' + reply)
                print('VISION_READY boot=' + boot, flush=True)
                last_sent = float('-inf')
                seq = 0
                while args.frames is None or seq < args.frames:
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError('Frame capture failed')
                    seq += 1
                    if seq > 2147483647:
                        raise RuntimeError('Frame sequence exhausted; restart with a new boot ID')
                    start = time.monotonic()
                    result = model.track(frame, **options)[0]
                    boxes = result.boxes
                    ids = [] if boxes.id is None else boxes.id.int().cpu().tolist()
                    people = len(boxes)
                    now = time.monotonic()
                    if now - last_sent >= 1 / args.send_hz:
                        height, width = frame.shape[:2]
                        messages = []
                        for track_id, (x1, y1, x2, y2) in zip(ids, boxes.xyxy.cpu().tolist()):
                            if not 1 <= track_id <= 2147483647:
                                raise RuntimeError('Track ID outside protocol range')
                            messages.append('[PI]POSITION@{}@{}@{}@{}@{}\n'.format(
                                boot, seq, track_id, normalized((x1 + x2) / 2, width),
                                normalized(y2, height)))
                        messages.append('[PI]VISION@{}@{}@{}@{}\n'.format(
                            boot, seq, people, len(ids)))
                        if people > 999:
                            raise RuntimeError('Observation count outside protocol range')
                        conn.sendall(''.join(messages).encode('ascii'))
                        ack = receive_line(stream)
                        expected = '[PI]VISION_ACK@{}@{}'.format(boot, seq)
                        if ack != expected:
                            raise RuntimeError('Unexpected observation reply: ' + ack)
                        last_sent = now
                        print('VISION seq={} people={} tracked={} inference_ms={:.1f} ACK'.format(
                            seq, people, len(ids), (now - start) * 1000), flush=True)
                    if args.display:
                        cv2.imshow('Mugunghwa - provisional tracks', result.plot())
                        if cv2.waitKey(1) & 0xff == ord('q'):
                            break
    finally:
        cap.release()
        if args.display:
            cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped', flush=True)
