"""Load the existing PyTorch model or our fixed-shape TensorRT engine."""
import json
from pathlib import Path


def engine_input_size(path):
    with open(path, 'rb') as stream:
        length = int.from_bytes(stream.read(4), 'little')
        if not 0 < length <= 1024 * 1024:
            raise ValueError('Expected an engine produced by build_engine.py with metadata')
        metadata = json.loads(stream.read(length))
    shape = metadata.get('imgsz')
    if not isinstance(shape, list) or len(shape) != 2 or any(type(s) is not int or s <= 0 or s % 32 for s in shape):
        raise ValueError('Invalid fixed engine image shape')
    return shape


def load_detector(path, image_size):
    task = 'pose' if '-pose' in Path(path).stem else 'detect'
    if Path(path).suffix == '.engine':
        image_size = engine_input_size(path)
        with open(path,'rb') as stream:
            metadata = json.loads(stream.read(int.from_bytes(stream.read(4),'little')))
        task = metadata.get('task','detect')
        if task not in ('detect','pose'):
            raise ValueError('Unsupported engine task')
        import numpy as np
        import tensorrt as trt
        # TensorRT 8.0's dtype map references NumPy's removed builtin-bool alias.
        if tuple(int(p) for p in trt.__version__.split('.')[:2]) <= (8, 2) and 'bool' not in np.__dict__:
            np.bool = bool
    from ultralytics import YOLO
    return YOLO(path, task=task), image_size


def pose_keypoints(result, boxes):
    if result.keypoints is None:
        return None
    # Ultralytics 8.3.0 turns an empty (0,51) pose tensor into (1,0,51).
    if not boxes:
        return []
    points = result.keypoints.data.cpu().tolist()
    if len(points) != len(boxes) or any(len(person)!=17 or any(len(k)!=3 for k in person) for person in points):
        raise ValueError('Expected one set of 17 COCO keypoints per box')
    return points
