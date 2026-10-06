import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jetson'))
from game.finish import FinishDetector

CONFIG = dict(roi=[[0,0],[1,0],[1,1],[0,1]], finish_line=[[.2,.5],[.8,.5]],
              finish_direction_point=[.5,.9])


class FinishTests(unittest.TestCase):
    def test_crossing_confirmed_once(self):
        d = FinishDetector(CONFIG)
        self.assertIsNone(d.update(1, [.5,.4], 0))
        self.assertIsNone(d.update(1, [.5,.502], .1))
        event = d.update(1, [.5,.52], .2)
        self.assertTrue(0 < event['crossed_at'] < .1)
        self.assertIsNone(d.update(1, [.5,.4], .3))
        self.assertIsNone(d.update(1, [.5,.6], .4))

    def test_wrong_direction_extension_and_gap(self):
        for points, times in [([[.5,.6],[.5,.4]], [0,.1]),
                              ([[.9,.4],[.9,.6]], [0,.1]),
                              ([[.5,.4],[.5,.6]], [0,1])]:
            d = FinishDetector(CONFIG)
            self.assertIsNone(d.update(1, points[0], times[0]))
            self.assertIsNone(d.update(1, points[1], times[1]))

    def test_jitter_and_destination_entry(self):
        d = FinishDetector(CONFIG)
        for i, y in enumerate([.4,.501,.499,.502,.498]):
            self.assertIsNone(d.update(1, [.5,y], i * .1))
        self.assertFalse(d.completed)
        self.assertIsNone(FinishDetector(CONFIG).update(1, [.5,.7], 0))

    def test_slow_crossing_and_roi_exclusion(self):
        d = FinishDetector(CONFIG)
        d.update(1, [.5,.4], 0)
        self.assertIsNone(d.update(1, [.5,.501], .1))
        for t in [.3,.5,.7]:
            self.assertIsNone(d.update(1, [.5,.505], t))
        self.assertIsNotNone(d.update(1, [.5,.52], .9))
        limited = dict(CONFIG, roi=[[.4,.3],[.6,.3],[.6,.7],[.4,.7]])
        d = FinishDetector(limited)
        self.assertIsNone(d.update(1, [.3,.4], 0))
        self.assertIsNone(d.update(1, [.3,.6], .1))


if __name__ == '__main__':
    unittest.main()
