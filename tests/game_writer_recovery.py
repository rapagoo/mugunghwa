"""Pi-only isolated writer outage/replay test; removes only its labelled fixture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import pymysql
ROOT=Path(__file__).resolve().parents[1]

def wait(predicate, timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.1)
    raise AssertionError('Writer condition timed out')

def main():
    config=json.loads((ROOT/'.runtime/db/writer.json').read_text())
    game='TEST-'+uuid.uuid4().hex
    r=dict(id=game,version=1,phase='finished',reason='timeout',started_at='2026-10-08T00:00:00.000Z',
        updated_at='2026-10-08T00:00:01.000Z',remaining=0,duration=1,epoch=1,kind='game_ended',participant=0,
        players=[dict(track_id=1,status='failed')],is_test=True)
    with tempfile.TemporaryDirectory() as directory:
        directory=Path(directory); journal=directory/'events.jsonl';private=directory/'private.json';log=directory/'writer.log'
        private.write_text(json.dumps(dict(config,password='invalid-isolated-test-password')));os.chmod(private,0o600)
        journal.write_text(json.dumps(r)+'\n')
        with log.open('w') as output:
            proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'pi/game_db_writer.py'),'--journal',str(journal),'--config',str(private)],stdout=output,stderr=output)
            try:
                wait(lambda:'DB_PENDING' in log.read_text())
                assert not journal.with_suffix('.offset').exists()
                private.write_text(json.dumps(config))
                wait(lambda:journal.with_suffix('.offset').exists())
                # Crash-safe replay: identical event appended a second time.
                with journal.open('a') as f:f.write(json.dumps(r)+'\n')
                wait(lambda:int(journal.with_suffix('.offset').read_text())==journal.stat().st_size)
                conn=pymysql.connect(**config,unix_socket='/run/mysqld/mysqld.sock',autocommit=False)
                try:
                    with conn.cursor() as c:
                        c.execute('SELECT is_test,phase,remaining_seconds FROM games WHERE id=%s',(game,));assert c.fetchone()==(1,'finished',0)
                        c.execute('SELECT COUNT(*) FROM events WHERE game_id=%s',(game,));assert c.fetchone()[0]==1
                    print('PASS writer: isolated auth failure retained journal, recovered/replayed once, checkpoint advanced')
                finally:conn.close()
            finally:
                proc.terminate();proc.wait(timeout=4)
                conn=pymysql.connect(**config,unix_socket='/run/mysqld/mysqld.sock',autocommit=False)
                try:
                    with conn.cursor() as c:
                        c.execute('SELECT is_test FROM games WHERE id=%s FOR UPDATE',(game,));row=c.fetchone()
                        if row:
                            assert row==(1,)
                            for table in ('events','participants'):c.execute('DELETE FROM '+table+' WHERE game_id=%s',(game,))
                            c.execute('DELETE FROM games WHERE id=%s',(game,))
                    conn.commit()
                finally:conn.close()

if __name__=='__main__':main()
