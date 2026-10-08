import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.game_bridge import enroll, observations

class GameBridgeTests(unittest.TestCase):
    def test_roi_only_unique_roster(self):
        state=dict(calibrated=True,validation=dict(observations=[dict(track_id=1,in_roi=True),
            dict(track_id=1,in_roi=True),dict(track_id=2,in_roi=False),dict(track_id=None,in_roi=True)]))
        self.assertEqual(enroll(state),[1])
        with self.assertRaises(ValueError):enroll(dict(calibrated=False))

    def test_stop_crossing_fails_and_old_phase_cannot_leak(self):
        expected=dict(version=4,phase='stop')
        state=dict(pose_trial=dict(**expected,observations=[dict(track_id=2,stop_candidate=True)]),
            candidates=[dict(track_id=1,phase='move',phase_version=3),dict(track_id=3,phase='stop',phase_version=4)])
        self.assertEqual(observations(state,expected),[(2,'FAIL'),(3,'FAIL')])
        self.assertEqual(observations(state,dict(version=5,phase='move')),[])

if __name__=='__main__':unittest.main()
