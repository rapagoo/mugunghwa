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
    if Path(path).suffix == '.engine':
        image_size = engine_input_size(path)
        import numpy as np
        import tensorrt as trt
        # TensorRT 8.0's dtype map references NumPy's removed builtin-bool alias.
        if tuple(int(p) for p in trt.__version__.split('.')[:2]) <= (8, 2) and 'bool' not in np.__dict__:
            np.bool = bool
    from ultralytics import YOLO
    return YOLO(path, task='detect'), image_size
