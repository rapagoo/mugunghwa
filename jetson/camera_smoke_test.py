"""Bounded webcam and YOLO check without a GUI or recording."""
import argparse
from pathlib import Path
import time

import cv2
import torch
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--frames', type=int, default=3)
    parser.add_argument('--imgsz', type=int, default=320)
    parser.add_argument('--model', default=str(Path(__file__).parent / 'examples/yolov8n.pt'))
    args = parser.parse_args()
    if args.frames <= 0 or args.imgsz <= 0:
        parser.error('frames and imgsz must be positive')
    if not Path(args.model).is_file():
        parser.error('model file does not exist: ' + args.model)

    print('CUDA_AVAILABLE', torch.cuda.is_available(), flush=True)
    cap = cv2.VideoCapture(args.camera)
    try:
        if not cap.isOpened():
            raise RuntimeError('Cannot open webcam')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        model = YOLO(args.model)
        for index in range(args.frames):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('Frame capture failed')
            start = time.monotonic()
            result = model.predict(frame, imgsz=args.imgsz,
                                   device=0 if torch.cuda.is_available() else 'cpu',
                                   verbose=False)[0]
            count = int((result.boxes.cls == 0).sum().item())
            print('INFERENCE_OK', index, 'shape', frame.shape, 'persons', count,
                  'seconds', round(time.monotonic() - start, 3), flush=True)
    finally:
        cap.release()


if __name__ == '__main__':
    main()
