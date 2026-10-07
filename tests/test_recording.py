import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.recording import TrialRecorder
from game.web import Monitor,create_server


class Frame:
    def copy(self): return self


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.rec=TrialRecorder(self.temp.name,encoder=lambda frame:b'jpeg')

    def tearDown(self):
        self.rec.close();self.temp.cleanup()

    def sample(self):
        self.rec.submit(dict(boxes=[],ids=[],keypoints=[],processing_ms=60,interval_ms=70),Frame())

    def finish(self):
        self.rec.stop();self.rec.thread.join(3)
        return self.rec.snapshot()

    def test_record_stop_keeps_evidence_and_summary(self):
        self.rec.start('still',dict(model='pose.engine'))
        self.sample();state=self.finish();self.sample()
        self.assertEqual(state['state'],'complete')
        self.assertEqual(state['written'],1)
        folder=Path(self.temp.name)/state['session_id']
        record=json.loads((folder/'samples.jsonl').read_text())
        self.assertEqual((folder/record['image']).read_bytes(),b'jpeg')
        self.assertEqual(json.loads((folder/'summary.json').read_text())['mean_interval_ms'],70)
        self.assertEqual(json.loads((folder/'metadata.json').read_text())['scenario'],'still')
        self.rec.start('arms',{})
        self.assertNotEqual(self.rec.snapshot()['session_id'],state['session_id'])

    def test_time_limit_without_frames_and_duplicate(self):
        self.rec.limit_s=.05
        with self.assertRaises(ValueError): self.rec.start('../bad',{})
        self.rec.start('turn',{})
        with self.assertRaises(ValueError): self.rec.start('arms',{})
        self.rec.thread.join(2)
        self.assertEqual(self.rec.snapshot()['state'],'complete')
        self.assertEqual(self.rec.snapshot()['stop_reason'],'time_limit')

    def test_io_error_is_not_success(self):
        def fail(frame): raise OSError('disk failed')
        self.rec.encoder=fail
        self.rec.start('still',{});self.sample();self.rec.thread.join(2)
        self.assertEqual(self.rec.snapshot()['state'],'error')
        self.assertEqual(self.rec.snapshot()['written'],0)

    def test_slow_disk_has_bounded_queue_and_reports_drops(self):
        gate=threading.Event()
        def slow(frame): gate.wait(2);return b'jpeg'
        self.rec.encoder=slow
        self.rec.start('mixed',{})
        for _ in range(60): self.sample()
        self.assertGreater(self.rec.snapshot()['dropped'],0)
        self.assertLessEqual(self.rec.queue.qsize(),16)
        gate.set();state=self.finish()
        self.assertEqual(state['written']+state['dropped'],60)

    def test_http_start_stop_and_request_guard(self):
        monitor=Monitor('camera')
        monitor.update(dict(state='running',completed_wall=time.monotonic(),width=640,height=480))
        database=type('DB',(),{'snapshot':lambda self:{}})()
        server=create_server('127.0.0.1',0,monitor,database,recorder=self.rec)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])
        headers={'Content-Type':'application/json','X-Mugunghwa-Calibration':'1'}
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url+'/api/recording/start',data=b'{"scenario":"still"}'))
            self.assertEqual(error.exception.code,403)
            with urlopen(Request(url+'/api/recording/start',data=b'{"scenario":"still"}',headers=headers)) as response:
                self.assertEqual(json.load(response)['state'],'recording')
            with urlopen(Request(url+'/api/recording/stop',data=b'{}',headers=headers)) as response:
                self.assertIn(json.load(response)['state'],('finalizing','complete'))
            with urlopen(url+'/api/recording') as response:
                self.assertIn(json.load(response)['state'],('finalizing','complete'))
        finally:
            monitor.close();server.shutdown();server.server_close();thread.join()
