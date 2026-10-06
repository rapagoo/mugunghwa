"""Extract a calibration frame without YOLO or a desktop display."""
import argparse
from pathlib import Path
import cv2
from game.source import FrameSource

parser = argparse.ArgumentParser(description=__doc__)
source = parser.add_mutually_exclusive_group()
source.add_argument('--camera', type=int, default=0)
source.add_argument('--video')
parser.add_argument('--output', required=True)
args = parser.parse_args()
capture = FrameSource(args.camera, args.video)
try:
    item = capture.read()
    if item is None:
        raise RuntimeError('Empty video')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), item[0]):
        raise RuntimeError('Cannot write snapshot')
    print('SNAPSHOT', output, 'size', item[0].shape[1], item[0].shape[0])
finally:
    capture.close()
