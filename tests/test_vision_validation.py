from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.validation import VisionValidation
from game.finish import FinishDetector

CONFIG=dict(roi=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],
            finish_line=[[.2,.5],[.8,.5]],finish_direction_point=[.5,.8])

def box(foot):
    x,y=foot
    return [x*640-10,y*480-80,x*640+10,y*480]

class ValidationTests(unittest.TestCase):
    def test_roi_events_and_gap_reappearance(self):
        d=VisionValidation(CONFIG,dict(number=1))
        f=FinishDetector(CONFIG)
        data=d.update([box([.05,.4])],[1],[.9],640,480,0,f)
        self.assertFalse(data['observations'][0]['in_roi'])
        data=d.update([box([.5,.4])],[1],[.9],640,480,.1,f)
        self.assertEqual(data['events'][-1]['kind'],'roi_enter')
        data=d.update([],[],[],640,480,.8,f)
        self.assertEqual(data['missing_ids'],[1])
        data=d.update([box([.5,.4])],[1],[.9],640,480,.9,f)
        self.assertEqual(data['events'][-1]['kind'],'reappeared')
        self.assertEqual(data['missing_ids'],[])

    def test_two_tracks_crossing_direction_and_reset(self):
        d=VisionValidation(CONFIG,dict(number=1))
        f=FinishDetector(CONFIG)
        d.update([box([.4,.4]),box([.6,.6])],[1,2],[.9,.8],640,480,0,f)
        data=d.update([box([.4,.6]),box([.6,.4])],[1,2],[.9,.8],640,480,.1,f)
        self.assertEqual(set(f.completed),{1})
        self.assertEqual([e['track_id'] for e in data['events'] if e['kind']=='finish_candidate'],[1])
        data=d.update([box([.4,.7])],[1],[.9],640,480,.2,f)
        self.assertEqual(len([e for e in data['events'] if e['kind']=='finish_candidate']),1)
        self.assertEqual(data['max_visible'],2)
        fresh=VisionValidation(CONFIG,dict(number=2)).update([],[],[],640,480,1,FinishDetector(CONFIG))
        self.assertEqual(fresh['events'],[])

    def test_unassigned_ids_and_bounded_history(self):
        d=VisionValidation(None,dict(number=1))
        data=d.update([box([.5,.5])],[],[.7],640,480,0,None)
        self.assertEqual(data['untracked'],1)
        self.assertIsNone(data['observations'][0]['in_roi'])
        for i in range(400):
            data=d.update([box([.5,.5])],[i],[.9],640,480,i*.01,None)
        self.assertLessEqual(len(d.tracks),256)
        self.assertLessEqual(len(data['events']),60)
