import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.detector import engine_input_size


class EngineInputTests(unittest.TestCase):
    def setUp(self):
        self.temp_base = Path(__file__).resolve().parents[1]/'.runtime'
        self.temp_base.mkdir(exist_ok=True)

    def test_clip_and_camera_fixed_shapes_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=str(self.temp_base)) as directory:
            path=Path(directory)/'model.engine'
            for shape in ([384,640],[480,640]):
                header=json.dumps(dict(imgsz=shape)).encode()
                path.write_bytes(len(header).to_bytes(4,'little')+header+b'engine')
                self.assertEqual(engine_input_size(path),shape)

    def test_raw_engine_or_invalid_tensor_shape_rejected(self):
        with tempfile.TemporaryDirectory(dir=str(self.temp_base)) as directory:
            path=Path(directory)/'model.engine'
            path.write_bytes(b'raw engine')
            with self.assertRaises(ValueError):
                engine_input_size(path)
            for shape in ([384,0],[360,640],['384',640],[True,640]):
                header=json.dumps(dict(imgsz=shape)).encode()
                path.write_bytes(len(header).to_bytes(4,'little')+header)
                with self.assertRaises(ValueError):
                    engine_input_size(path)


if __name__ == '__main__':
    unittest.main()
