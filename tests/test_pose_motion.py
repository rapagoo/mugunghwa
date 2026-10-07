import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'jetson'))
from game.pose_motion import PoseMotionTrial


class PoseMotionTests(unittest.TestCase):
    def setUp(self):
        self.trial = PoseMotionTrial()
        self.command = dict(version=1, phase='stop', requested_at=0)

    def sample(self, t, wrist=0, shift=0, tid=1, confidence=1, inside=True):
        points = [[200+shift, 150+j*8, confidence] for j in range(17)]
        points[9][0] += wrist
        return self.trial.update([[150+shift, 100, 250+shift, 400]], [tid],
            [dict(in_roi=inside, candidate=False)], [points], t, self.command)

    def test_jitter_and_transient_do_not_trigger(self):
        self.sample(0)
        for i in range(1, 20):
            out = self.sample(i*.07, wrist=2*(i%2), shift=i%2)
        self.assertFalse(out['events'])
        self.sample(1.4, wrist=45)
        out = self.sample(1.47)
        self.assertFalse(out['events'])

    def test_wrist_inside_static_box_and_latch(self):
        self.sample(0)
        for i in range(1, 8):
            out = self.sample(i*.07, wrist=40)
        self.assertTrue(out['observations'][0]['stop_candidate'])
        self.assertEqual(len(out['events']), 1)
        self.assertTrue(self.sample(.6)['observations'][0]['stop_candidate'])
        self.command = dict(version=2, phase='move', requested_at=.7)
        self.assertFalse(self.sample(.7)['events'])

    def test_slow_cumulative_motion_and_body_translation(self):
        self.sample(0)
        for i in range(1, 30):
            out = self.sample(i*.07, wrist=i*2)
        self.assertTrue(out['events'])
        self.setUp(); self.sample(0)
        for i in range(1, 8):
            out = self.sample(i*.07, shift=25)
        self.assertTrue(out['events'])

    def test_low_confidence_resets_confirmation(self):
        self.sample(0)
        self.sample(.07, wrist=40)
        out = self.sample(.14, wrist=40, confidence=.1)
        self.assertEqual(out['observations'][0]['reason'], 'low_confidence')
        out = self.sample(.21, wrist=40)
        self.assertFalse(out['events'])

    def test_new_id_and_gap_do_not_rebase(self):
        self.sample(0)
        out = self.sample(.07, tid=2, wrist=50)
        self.assertEqual(out['observations'][0]['reason'], 'baseline_missing')
        out = self.sample(1, wrist=50)
        self.assertEqual(out['observations'][0]['reason'], 'tracking_gap')
        out = self.sample(1.07)
        self.assertEqual(out['observations'][0]['status'], 'hold')

    def test_stale_capture_cannot_set_baseline(self):
        self.command['requested_at'] = 1
        self.sample(.9)
        out = self.sample(1.01)
        self.assertTrue(out['observations'][0]['stop_baseline_ready'])

    def test_outside_and_missing_pose(self):
        out = self.sample(0, inside=False)
        self.assertFalse(out['observations'][0]['stop_baseline_ready'])
        out = self.trial.update([[150,100,250,400]], [1],
            [dict(in_roi=True,candidate=False)], None, .1, self.command)
        self.assertEqual(out['observations'][0]['reason'], 'pose_unavailable')

    def test_missing_wrist_is_not_evidence_of_stillness(self):
        self.sample(0)
        points = [[200,150+j*8,1] for j in range(17)]
        # Core joints still observable: score covers those only, not unseen arms.
        for j in (7,8,9,10): points[j][2] = 0
        out = self.trial.update([[150,100,250,400]], [1],
            [dict(in_roi=True,candidate=False)], [points], .07, self.command)
        self.assertFalse(out['events'])
        self.assertEqual(out['observations'][0]['valid_joints'], 8)
        self.assertEqual(out['observations'][0]['status'], 'hold')


if __name__ == '__main__':
    unittest.main()
