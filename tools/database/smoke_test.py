"""Pi-only transaction test; synthetic game is labelled and removed by default."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import uuid
import pymysql

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='.runtime/db/writer.json')
    parser.add_argument('--keep',action='store_true',help='keep labelled fixture temporarily for browser verification')
    parser.add_argument('--cleanup',help='remove a previously kept test game by ID')
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    connection=pymysql.connect(**config,unix_socket='/run/mysqld/mysqld.sock',charset='utf8mb4',autocommit=False)
    try:
        with connection.cursor() as cursor:
            if args.cleanup:
                cursor.execute('SELECT is_test FROM games WHERE id=%s FOR UPDATE',(args.cleanup,))
                row=cursor.fetchone()
                if not row or not row[0]:
                    raise ValueError('Refusing to delete non-test/missing game')
                for table in ('events','participants'):
                    cursor.execute('DELETE FROM '+table+' WHERE game_id=%s',(args.cleanup,))
                cursor.execute('DELETE FROM games WHERE id=%s',(args.cleanup,))
                connection.commit()
                print('Test fixture removed')
                return
            game_id='TEST-'+uuid.uuid4().hex[:12]
            now=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
            cursor.execute('INSERT INTO games (id,phase,started_at,remaining_seconds,updated_at,authority,is_test) VALUES (%s,%s,%s,%s,%s,%s,TRUE)',(game_id,'running',now,42,now,'PI'))
            for participant,status in [('TEST-A','passed'),('TEST-B','failed')]:
                cursor.execute('INSERT INTO participants VALUES (%s,%s,%s,%s,%s)',(game_id,participant,'시험 참가자 '+participant,status,now))
                cursor.execute('INSERT INTO events (game_id,event_key,kind,participant_id,occurred_at) VALUES (%s,%s,%s,%s,%s)',(game_id,game_id+'-'+participant,status,participant,now))
            cursor.execute('SELECT COUNT(*) FROM participants WHERE game_id=%s',(game_id,))
            assert cursor.fetchone()[0]==2
            if args.keep:
                connection.commit()
                print(game_id)
            else:
                connection.rollback()
                print('Writer transaction verified; fixture rolled back')
    finally:
        connection.close()

if __name__=='__main__':
    main()
