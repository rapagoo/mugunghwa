"""Validated, normalized camera geometry; no game verdicts."""
import json
import math
from pathlib import Path


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def inside(p, polygon):
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(cross(a, b, p)) < 1e-9 and all(
                min(a[i], b[i]) - 1e-9 <= p[i] <= max(a[i], b[i]) + 1e-9 for i in (0, 1)):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            if p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
                hit = not hit
    return hit


def validate(config):
    if not isinstance(config, dict):
        raise ValueError('Calibration must be a JSON object')
    def point(p):
        return (isinstance(p, list) and len(p) == 2 and all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in p))
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported calibration schema')
    ref = config.get('reference_size', [])
    if not isinstance(ref, list) or len(ref) != 2 or any(type(v) is not int or v <= 0 for v in ref):
        raise ValueError('Invalid reference_size')
    roi = config.get('roi', [])
    line = config.get('finish_line', [])
    if not isinstance(roi, list) or not 3 <= len(roi) <= 32 or not all(map(point, roi)):
        raise ValueError('ROI needs 3..32 normalized points')
    if len({tuple(p) for p in roi}) != len(roi):
        raise ValueError('ROI contains duplicate points')
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(roi, roi[1:] + roi[:1]))
    if abs(area) < 1e-6:
        raise ValueError('ROI has no area')
    # Non-adjacent edges may neither touch nor intersect.
    edges = list(zip(roi, roi[1:] + roi[:1]))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if (cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0
                    and all(max(min(a[k], b[k]), min(c[k], d[k])) <=
                            min(max(a[k], b[k]), max(c[k], d[k])) for k in (0, 1))):
                raise ValueError('ROI edges intersect')
    if not isinstance(line, list) or len(line) != 2 or not all(map(point, line)) or line[0] == line[1]:
        raise ValueError('Finish line needs two distinct normalized points')
    direction = config.get('finish_direction_point')
    if not point(direction) or abs(cross(*line, direction)) < 1e-6:
        raise ValueError('Select the destination side away from the finish line')
    return config


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def check_size(config, width, height):
    rw, rh = config['reference_size']
    if abs((width / height) / (rw / rh) - 1) > 0.01:
        raise ValueError('Calibration aspect ratio differs; calibrate this source again')


def overlay(frame, config):
    import cv2
    import numpy as np
    height, width = frame.shape[:2]
    check_size(config, width, height)
    def pixels(points):
        return np.array([[round(x * (width - 1)), round(y * (height - 1))] for x, y in points], np.int32)
    cv2.polylines(frame, [pixels(config['roi'])], True, (50, 210, 90), 2)
    line = pixels(config['finish_line'])
    cv2.line(frame, tuple(line[0]), tuple(line[1]), (0, 190, 255), 3)
    mid = ((line[0] + line[1]) / 2).astype(int)
    target = pixels([config['finish_direction_point']])[0]
    cv2.arrowedLine(frame, tuple(mid), tuple(target), (0, 190, 255), 2)
    return frame
