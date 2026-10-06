import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.web import Monitor, GameDatabase, create_server
from game.mariadb_store import DatabaseUnavailable


class WebTests(unittest.TestCase):
    def test_database_failure_does_not_expose_details_or_break_preview(self):
        class FailedDatabase:
            def snapshot(self):
                raise DatabaseUnavailable('private internal error')
        monitor=Monitor('video')
        monitor.update({'people':1},b'jpeg')
        server=create_server('127.0.0.1',0,monitor,FailedDatabase())
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_port)
            with self.assertRaises(HTTPError) as caught:
                urlopen(url+'/api/game')
            self.assertEqual(caught.exception.code,503)
            self.assertEqual(caught.exception.read(),b'Database unavailable')
            caught.exception.close()
            with urlopen(url+'/frame.jpg') as response:
                self.assertEqual(response.read(),b'jpeg')
        finally:
            monitor.close()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_database_persistence_and_no_vision_verdict(self):
        base=Path(__file__).resolve().parents[1]/'.runtime'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as folder:
            path=Path(folder)/'game.db'
            db=GameDatabase(path)
            self.assertIsNone(db.snapshot()['game'])
            monitor=Monitor('video')
            monitor.update({'candidates':[{'track_id':1}]})
            self.assertEqual(db.snapshot()['participants'],[])
            with closing(sqlite3.connect(str(path))) as connection:
                connection.execute("INSERT INTO games VALUES ('g1','running',NULL,42,'2026-10-06T10:00:00Z','PI')")
                connection.execute("INSERT INTO participants VALUES ('g1','p1','A','passed','2026-10-06T10:00:00Z')")
                connection.commit()
            saved=GameDatabase(path).snapshot()
            self.assertEqual(saved['game']['remaining_seconds'],42)
            self.assertEqual(saved['participants'][0]['status'],'passed')
            server=create_server('127.0.0.1',0,monitor,db)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)
                with urlopen(url+'/api/game') as response:
                    self.assertEqual(json.load(response),saved)
                monitor.update({'people':2},b'cached-jpeg')
                with urlopen(url+'/frame.jpg') as response:
                    self.assertEqual(response.read(),b'cached-jpeg')
                with urlopen(url+'/stream.mjpg', timeout=2) as response:
                    self.assertIn('multipart/x-mixed-replace',response.headers['Content-Type'])
                    self.assertEqual(response.readline(),b'--frame\r\n')
                    self.assertEqual(response.readline(),b'Content-Type: image/jpeg\r\n')
                    self.assertEqual(response.readline(),b'Content-Length: 11\r\n')
                    self.assertEqual(response.readline(),b'\r\n')
                    self.assertEqual(response.read(11),b'cached-jpeg')
                with urlopen(url+'/') as response:
                    self.assertIn('무궁화'.encode(),response.read())
            finally:
                monitor.close()
                server.shutdown()
                server.server_close()
                thread.join()


if __name__=='__main__':
    unittest.main()

