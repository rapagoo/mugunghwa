"""Durable Pi game journal -> transactional MariaDB. No game decisions here."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
import pymysql


def apply(connection, record):
    r = record
    with connection.cursor() as cursor:
        cursor.execute('SELECT state_version FROM games WHERE id=%s FOR UPDATE', (r['id'],))
        old = cursor.fetchone()
        if old and old[0] >= r['version']:
            return
        terminal = r['phase'] in ('finished', 'aborted')
        cursor.execute('''INSERT INTO games
            (id,phase,started_at,remaining_seconds,updated_at,authority,is_test,state_version,duration_seconds,ended_at,end_reason)
            VALUES (%s,%s,%s,%s,%s,'PI',%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE phase=VALUES(phase),remaining_seconds=VALUES(remaining_seconds),
            updated_at=VALUES(updated_at),state_version=VALUES(state_version),ended_at=VALUES(ended_at),end_reason=VALUES(end_reason)''',
            (r['id'],r['phase'],r['started_at'],r['remaining'],r['updated_at'],bool(r.get('is_test')),
             r['version'],r['duration'],r['updated_at'] if terminal else None,r['reason'] or None))
        for index, player in enumerate(r['players'],1):
            pid = 'P%02d' % index
            cursor.execute('''INSERT INTO participants (game_id,id,name,status,updated_at,track_id,source_epoch)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status=VALUES(status),updated_at=VALUES(updated_at)''',
                (r['id'],pid,'참가자 %d (ID %d)' % (index,player['track_id']),player['status'],r['updated_at'],player['track_id'],r['epoch']))
        # Ticks persist remaining time without flooding the event list.
        if r['kind'] not in ('tick','device_ack'):
            cursor.execute('INSERT IGNORE INTO events (game_id,event_key,kind,participant_id,occurred_at) VALUES (%s,%s,%s,%s,%s)',
                (r['id'],r['id']+':'+str(r['version']),r['kind'],'P%02d'%r['participant'] if r['participant'] else None,r['updated_at']))
        if not r.get('is_test'):
            cursor.execute('''INSERT INTO device_status (id,connection_state,last_seen_at,updated_at)
                VALUES ('PI','connected',%s,%s) ON DUPLICATE KEY UPDATE
                connection_state='connected',last_seen_at=VALUES(last_seen_at),updated_at=VALUES(updated_at)''',
                (r['updated_at'],r['updated_at']))
            for device in r.get('devices',[]):
                if not device['at']:
                    continue
                cursor.execute('''INSERT INTO device_status (id,connection_state,last_seen_at,last_ack,updated_at)
                    VALUES (%s,'connected',%s,%s,%s) ON DUPLICATE KEY UPDATE
                    connection_state='connected',last_seen_at=VALUES(last_seen_at),last_ack=VALUES(last_ack),updated_at=VALUES(updated_at)''',
                    (device['id'],device['at'],device['ack'],r['updated_at']))


def run(journal, config_file):
    journal = Path(journal)
    lock = journal.with_suffix('.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Writer already running'); return
    checkpoint = journal.with_suffix('.offset')
    offset = int(checkpoint.read_text()) if checkpoint.exists() else 0
    if offset > journal.stat().st_size:
        raise RuntimeError('Journal truncated; refusing silent offset reset')
    previous_error = None
    while True:
        with journal.open('rb') as source:
            source.seek(offset)
            line = source.readline()
            end = source.tell()
        if not line.endswith(b'\n'):
            time.sleep(.2); continue
        connection = None
        try:
            record = json.loads(line)
            config = json.loads(Path(config_file).read_text(encoding='utf-8'))
            connection = pymysql.connect(**config,unix_socket='/run/mysqld/mysqld.sock',
                charset='utf8mb4',autocommit=False,connect_timeout=2,read_timeout=2,write_timeout=2)
            apply(connection, record)
            connection.commit()
            temp = checkpoint.with_suffix('.offset.tmp')
            with temp.open('w') as f:
                f.write(str(end)); f.flush(); os.fsync(f.fileno())
            temp.replace(checkpoint)
            offset = end
            if previous_error is not None:
                print('DB reconnected; journal replay resumed',flush=True)
            previous_error = None
        except (pymysql.MySQLError, OSError, ValueError, KeyError) as error:
            # Error code only: never print credentials or SQL content.
            code = error.args[0] if isinstance(error,pymysql.MySQLError) else type(error).__name__
            if code != previous_error:
                print('DB_PENDING',code,'journal retained; retrying',flush=True)
            previous_error = code
            time.sleep(2)
        finally:
            if connection is not None:
                connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal',required=True)
    parser.add_argument('--config',required=True)
    args = parser.parse_args()
    run(args.journal,args.config)
