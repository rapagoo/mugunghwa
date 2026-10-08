"""Pi MariaDB transaction/replay checks; all synthetic rows rolled back."""
import json
from pathlib import Path
import sys
import uuid
import pymysql
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pi'))
from game_db_writer import apply

config=json.loads((ROOT/'.runtime/db/writer.json').read_text())
conn=pymysql.connect(**config,unix_socket='/run/mysqld/mysqld.sock',charset='utf8mb4',autocommit=False)
r=dict(id='TEST-'+uuid.uuid4().hex,version=1,phase='move',reason='',started_at='2026-10-08T00:00:00.000Z',
       updated_at='2026-10-08T00:00:00.000Z',remaining=180,duration=180,epoch=1,kind='game_started',
       participant=0,players=[dict(track_id=11,status='playing'),dict(track_id=22,status='playing')],is_test=True)
try:
    apply(conn,r);apply(conn,r)
    with conn.cursor() as c:
        c.execute('SELECT COUNT(*) FROM events WHERE game_id=%s',(r['id'],));assert c.fetchone()[0]==1
    old=r.copy();r.update(version=2,phase='finished',reason='timeout',remaining=0,kind='game_ended')
    r['players']=[dict(track_id=11,status='passed'),dict(track_id=22,status='failed')]
    apply(conn,r);apply(conn,old)
    with conn.cursor() as c:
        c.execute('SELECT phase,remaining_seconds,state_version FROM games WHERE id=%s',(r['id'],));assert c.fetchone()==('finished',0,2)
        c.execute('SELECT status FROM participants WHERE game_id=%s ORDER BY id',(r['id'],));assert c.fetchall()==(('passed',),('failed',))
    print('PASS MariaDB atomic snapshot, duplicate replay, old-version rejection; all fixtures rolled back')
finally:
    conn.rollback();conn.close()
