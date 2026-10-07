import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from analyze_pose_recording import analyze


class RecordingAnalysisTests(unittest.TestCase):
    def run_analysis(self,rows):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'metadata.json').write_text(json.dumps(dict(scenario='arms')))
            (folder/'samples.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
            return analyze(folder)

    def row(self,t,x=10):
        return dict(source_wall=t,boxes=[[0,0,100,100]],ids=[1],interval_ms=70,
                    keypoints=[[[x,10,.9]]*17])

    def test_stationary_and_displacement_are_not_accuracy_claims(self):
        report=self.run_analysis([self.row(1),self.row(1.07),self.row(1.14,20)])
        self.assertEqual(report['saved_samples'],3)
        self.assertEqual(report['mean_visible_keypoints'],17)
        self.assertAlmostEqual(report['adjacent_joint_displacement_p95_body_heights'],.1)
        self.assertEqual(report['same_id_gaps'],[])

    def test_gap_excludes_displacement_and_empty_record_is_supported(self):
        report=self.run_analysis([self.row(1),self.row(2,90)])
        self.assertEqual(len(report['same_id_gaps']),1)
        self.assertIsNone(report['adjacent_joint_displacement_p95_body_heights'])
        report=self.run_analysis([])
        self.assertEqual(report['saved_samples'],0)
        self.assertIsNone(report['mean_interval_ms'])
