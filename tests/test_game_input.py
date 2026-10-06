"""Geometry safety and real video decoder EOF/restart/media-clock checks."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jetson'))
from game import geometry

CONFIG = dict(schema_version=1, reference_size=[640, 480],
              roi=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
              finish_line=[[0.1, 0.3], [0.9, 0.3]], finish_direction_point=[0.5, 0.15])


class GeometryTests(unittest.TestCase):
    def test_inside_boundary_and_outside(self):
        geometry.validate(CONFIG)
        self.assertTrue(geometry.inside((0.5, 0.5), CONFIG['roi']))
        self.assertTrue(geometry.inside((0.1, 0.5), CONFIG['roi']))
        self.assertFalse(geometry.inside((0.95, 0.5), CONFIG['roi']))
        geometry.check_size(CONFIG, 1280, 960)
        with self.assertRaises(ValueError):
            geometry.check_size(CONFIG, 1920, 1080)

    def test_unsafe_geometry(self):
        for field, value in [('roi', [[0, 0], [1, 1], [0, 1], [1, 0]]),
                             ('roi', [[0, 0], [1, 0], [float('nan'), 1]]),
                             ('finish_line', [[0, 0], [0, 0]]),
                             ('finish_direction_point', [0.5, 0.3]),
                             ('reference_size', [0, 480])]:
            config = copy.deepcopy(CONFIG)
            config[field] = value
            with self.assertRaises(ValueError):
                geometry.validate(config)


class DecoderTests(unittest.TestCase):
    def test_eof_restart_and_loop_clock(self):
        import cv2
        import numpy as np
        from game.source import FrameSource
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'fixture.avi')
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
            self.assertTrue(writer.isOpened())
            for i in range(4):
                writer.write(np.full((48, 64, 3), i * 40, dtype=np.uint8))
            writer.release()
            capture = FrameSource(video=path)
            try:
                frames = [capture.read() for _ in range(4)]
                self.assertIsNone(capture.read())
                self.assertTrue(all(b[1] > a[1] for a, b in zip(frames, frames[1:])))
                self.assertAlmostEqual(frames[-1][1], 0.3, places=2)
                capture.restart()
                self.assertEqual(capture.read()[2], 1)
                capture.loop = True
                for _ in range(3):
                    capture.read()
                item = capture.read()
                self.assertEqual(item[2], 2)
                self.assertAlmostEqual(item[1], 0, places=2)
            finally:
                capture.close()


if __name__ == '__main__':
    unittest.main()
