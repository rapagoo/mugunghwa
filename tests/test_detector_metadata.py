import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.detector import load_detector,engine_input_size,pose_keypoints


class EngineMetadataTests(unittest.TestCase):
    def test_empty_pose_has_no_phantom_person(self):
        result=SimpleNamespace(keypoints=SimpleNamespace(data=None))
        self.assertEqual(pose_keypoints(result,[]),[])
        self.assertIsNone(pose_keypoints(SimpleNamespace(keypoints=None),[]))

    def test_pose_box_alignment(self):
        points=[[[1,2,.8]]*17]
        tensor=SimpleNamespace(tolist=lambda:points)
        result=SimpleNamespace(keypoints=SimpleNamespace(data=SimpleNamespace(cpu=lambda:tensor)))
        self.assertEqual(pose_keypoints(result,[[0,0,1,1]]),points)
        with self.assertRaises(ValueError): pose_keypoints(result,[[0,0,1,1]]*2)

    def write_engine(self,path,metadata):
        header=json.dumps(metadata).encode()
        path.write_bytes(len(header).to_bytes(4,'little')+header+b'fake-engine')

    def test_pose_task_is_not_forced_to_detect(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'neutral-name.engine'
            self.write_engine(path,dict(imgsz=[480,640],task='pose',kpt_shape=[17,3]))
            fake=SimpleNamespace(YOLO=lambda model,task: dict(model=model,task=task))
            with patch.dict(sys.modules,{'ultralytics':fake,'tensorrt':SimpleNamespace(__version__='8.4'),
                                        'numpy':SimpleNamespace()}):
                model,size=load_detector(path,320)
            self.assertEqual(model['task'],'pose')
            self.assertEqual(size,[480,640])

    def test_legacy_detect_and_bad_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'original.engine'
            self.write_engine(path,dict(imgsz=[480,640],task='detect'))
            self.assertEqual(engine_input_size(path),[480,640])
            self.write_engine(path,dict(imgsz=[481,640],task='pose'))
            with self.assertRaises(ValueError): engine_input_size(path)

    def test_unsupported_task_rejected_before_gpu_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'invalid.engine'
            self.write_engine(path,dict(imgsz=[480,640],task='segment'))
            with self.assertRaises(ValueError): load_detector(path,640)
