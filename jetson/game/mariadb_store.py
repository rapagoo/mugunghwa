"""Read-only MariaDB adapter. Credentials live outside Git; no schema writes."""
import json
from datetime import datetime, timezone
from pathlib import Path


class DatabaseUnavailable(Exception):
    pass


class MariaGameDatabase:
    def __init__(self, config_file):
        import pymysql
        self.driver = pymysql
        self.config = json.loads(Path(config_file).read_text(encoding='utf-8'))
        required = {'host','port','user','password','database'}
        if set(self.config) != required:
            raise ValueError('DB config requires host, port, user, password, database only')

    def snapshot(self):
        try:
            connection = self.driver.connect(**self.config, charset='utf8mb4',
                cursorclass=self.driver.cursors.DictCursor, connect_timeout=2,
                read_timeout=2, write_timeout=2, autocommit=False)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
                    cursor.execute('SELECT * FROM games ORDER BY updated_at DESC,id DESC LIMIT 1')
                    game = cursor.fetchone()
                    cursor.execute('SELECT * FROM device_status ORDER BY id')
                    devices = cursor.fetchall()
                    now=datetime.now(timezone.utc)
                    for device in devices:
                        seen=device.get('last_seen_at')
                        try: age=(now-datetime.fromisoformat(seen.replace('Z','+00:00'))).total_seconds() if seen else None
                        except (ValueError,TypeError): age=None
                        device['age_seconds']=age
                        # Historical receipt is not proof that a silent board is connected now.
                        if age is None or age>10: device['connection_state']='unknown'
                    players, events = [], []
                    if game:
                        cursor.execute('SELECT * FROM participants WHERE game_id=%s ORDER BY id',(game['id'],))
                        players = cursor.fetchall()
                        cursor.execute('SELECT * FROM events WHERE game_id=%s ORDER BY id DESC LIMIT 30',(game['id'],))
                        events = cursor.fetchall()
                    return dict(connected=True, backend='mariadb', game=game,
                                participants=list(players),events=list(events),devices=list(devices))
            finally:
                connection.close()
        except self.driver.MySQLError:
            # Do not expose account details or server errors to HTTP clients/logs.
            raise DatabaseUnavailable('Database unavailable') from None
