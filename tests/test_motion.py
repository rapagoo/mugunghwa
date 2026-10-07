import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.motion import MotionTrial


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.trial = MotionTrial()
        self.command = dict(version=1,phase='move',requested_at=0)

    def sample(self,t,x=200,ids=(1,),inside=True,candidate=False):
        return self.trial.update([[x,100,x+100,400] for _ in ids],list(ids),
            [dict(in_roi=inside,candidate=candidate) for _ in ids],640,480,t,self.command)

    def test_still_jitter_and_motion(self):
        for i in range(12):
            out=self.sample(i*.07,200+i%2)
        self.assertEqual(out['observations'][0]['status'],'still')
        for i in range(12,22):
            out=self.sample(i*.07,200+(i-12)*6)
        self.assertEqual(out['observations'][0]['status'],'moving')
        self.assertFalse(out['events'])

    def test_grace_candidate_latch_and_phase_reset(self):
        self.command=dict(version=2,phase='stop',requested_at=0)
        for i in range(15): self.sample(i*.07)
        for i in range(15,25): out=self.sample(i*.07,230)
        self.assertTrue(out['observations'][0]['stop_candidate'])
        self.assertEqual(len(out['events']),1)
        self.command=dict(version=3,phase='move',requested_at=2)
        out=self.sample(2,250)
        self.assertFalse(out['observations'][0]['stop_candidate'])
        self.assertFalse(out['events'])

    def test_gap_outside_finished_and_untracked(self):
        self.command=dict(version=2,phase='stop',requested_at=0)
        for i in range(15): self.sample(i*.07)
        out=self.sample(2,300)
        self.assertEqual(out['observations'][0]['status'],'pending')
        self.assertFalse(out['observations'][0]['stop_candidate'])
        for i in range(30,45): out=self.sample(i*.07,300,inside=False)
        self.assertFalse(out['events'])
        out=self.sample(4,400,candidate=True)
        self.assertFalse(out['observations'][0]['stop_baseline_ready'])
        out=self.sample(4.1,ids=())
        self.assertEqual(out['missing_ids'],[])
        out=self.trial.update([[1,1,50,100]],[],[dict(in_roi=True,candidate=False)],640,480,5,self.command)
        self.assertEqual(out['observations'][0]['status'],'pending')
        self.assertFalse(out['events'])

    def test_two_people_only_one_moves(self):
        for i in range(15):
            self.trial.update([[200,100,300,400],[400+i*6,100,500+i*6,400]],
                [1,2],[dict(in_roi=True,candidate=False)]*2,640,480,i*.07,self.command)
        out=self.trial.update([[200,100,300,400],[490,100,590,400]],
                [1,2],[dict(in_roi=True,candidate=False)]*2,640,480,1.05,self.command)
        self.assertEqual([o['status'] for o in out['observations']],['still','moving'])
