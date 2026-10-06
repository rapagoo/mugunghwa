#!/bin/bash
# Run on Pi as root. Does not reset existing DBs/users or alter MCU programs.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
config_dir="$repo/.runtime/db"
if [ "$(id -u)" != 0 ]; then echo 'Run with sudo bash tools/database/setup_pi.sh'; exit 1; fi
if [ -f "$config_dir/writer.json" ] || [ -f "$config_dir/web.json" ]; then
    echo 'Existing DB credentials found; refusing to recreate accounts. See docs/database.md.'; exit 1
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y mariadb-server python3-pymysql
systemctl enable --now mariadb
mariadb < "$repo/database/001_schema.sql"
install -d -m 700 -o pi -g pi "$config_dir"
python3 - "$config_dir" <<'PY'
import json, os, pathlib, secrets, subprocess, sys
directory = pathlib.Path(sys.argv[1])
writer, reader = secrets.token_hex(24), secrets.token_hex(24)
# Account host restrictions: writer only Pi loopback, web reader only Jetson.
sql = f"""
CREATE USER 'mugunghwa_writer'@'localhost' IDENTIFIED BY '{writer}';
CREATE USER 'mugunghwa_web'@'10.10.16.120' IDENTIFIED BY '{reader}';
GRANT SELECT, INSERT, UPDATE, DELETE ON mugunghwa.* TO 'mugunghwa_writer'@'localhost';
GRANT SELECT ON mugunghwa.* TO 'mugunghwa_web'@'10.10.16.120';
"""
subprocess.run(['mariadb'], input=sql, text=True, check=True, stdout=subprocess.DEVNULL)
for filename,user,password,host in [('writer.json','mugunghwa_writer',writer,'localhost'),
                                   ('web.json','mugunghwa_web',reader,'10.10.16.90')]:
    path = directory / filename
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(dict(host=host,port=3306,user=user,password=password,database='mugunghwa'), f)
    import pwd
    owner = pwd.getpwnam('pi')
    os.chown(path,owner.pw_uid,owner.pw_gid)
PY
# Bind only the Pi LAN address; local writer uses Unix socket.
if [ -e /etc/mysql/mariadb.conf.d/90-mugunghwa.cnf ]; then
    echo 'Existing project bind configuration found; inspect it manually.'; exit 1
fi
printf '[mysqld]\nbind-address = 10.10.16.90\n' > /etc/mysql/mariadb.conf.d/90-mugunghwa.cnf
systemctl restart mariadb
systemctl is-active mariadb
echo 'MariaDB ready. Private writer/web JSON files created in .runtime/db (not printed).'
