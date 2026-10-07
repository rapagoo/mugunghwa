import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.calibration_store import CalibrationStore,CalibrationConflict
from game.web import Monitor,create_server

CONFIG=dict(schema_version=1,reference_size=[640,480],roi=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],
            finish_line=[[.2,.6],[.8,.6]],finish_direction_point=[.5,.8])

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime'
        base.mkdir(exist_ok=True)
        self.folder=tempfile.TemporaryDirectory(dir=str(base))
        self.path=Path(self.folder.name)/'camera.json'
        self.store=CalibrationStore(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_persistence_conflicts_and_validation_preserve_previous_config(self):
        saved=self.store.save(CONFIG,0,640,480)
        self.assertEqual(CalibrationStore(self.path).snapshot()['config'],CONFIG)
        with self.assertRaises(CalibrationConflict):
            self.store.save(CONFIG,0,640,480)
        with self.assertRaises(ValueError):
            self.store.save(CONFIG,1,960,540)
        invalid=dict(CONFIG,roi=[[.1,.1],[.9,.9],[.9,.1],[.1,.9]])
        with self.assertRaises(ValueError):
            self.store.save(invalid,1,640,480)
        self.assertEqual(self.store.snapshot(),saved)
        self.store.save(None,1,640,480)
        self.assertFalse(self.path.exists())
        self.assertIsNone(self.store.snapshot()['config'])

    def test_http_save_guards_and_camera_snapshot(self):
        monitor=Monitor('camera')
        monitor.update(dict(width=640,height=480),b'preview',b'raw')
        server=create_server('127.0.0.1',0,monitor,None,self.store)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        payload=json.dumps(dict(config=CONFIG,expected_revision=0)).encode()
        def post(headers,data=payload):
            return urlopen(Request(url+'/api/calibration',data=data,headers=headers),timeout=3)
        headers={'Content-Type':'application/json','X-Mugunghwa-Calibration':'1'}
        try:
            for bad in ({'Content-Type':'application/json'},dict(headers,Origin='http://other-site')):
                with self.assertRaises(HTTPError) as error:
                    post(bad)
                self.assertEqual(error.exception.code,403)
                error.exception.close()
            with post(headers) as response:
                self.assertEqual(json.load(response)['revision'],1)
            with self.assertRaises(HTTPError) as error:
                post(headers)
            self.assertEqual(error.exception.code,409)
            error.exception.close()
            with urlopen(url+'/camera.jpg') as response:
                self.assertEqual(response.read(),b'raw')
            with urlopen(url+'/api/calibration') as response:
                self.assertEqual(json.load(response)['config'],CONFIG)
        finally:
            monitor.close(); server.shutdown(); server.server_close(); thread.join()
