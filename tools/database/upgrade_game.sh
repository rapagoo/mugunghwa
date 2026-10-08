#!/bin/bash
# Preserve all data/passwords. Restrict the reader to the current Jetson address.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
if [ "$(id -u)" != 0 ]; then echo 'Run with sudo bash tools/database/upgrade_game.sh'; exit 1; fi
mariadb < "$repo/database/002_game_state.sql"
old=$(mariadb -N -e "SELECT COUNT(*) FROM mysql.user WHERE User='mugunghwa_web' AND Host='10.10.16.120'")
new=$(mariadb -N -e "SELECT COUNT(*) FROM mysql.user WHERE User='mugunghwa_web' AND Host='10.10.16.130'")
if [ "$old" = 1 ] && [ "$new" = 0 ]; then
    mariadb -e "RENAME USER 'mugunghwa_web'@'10.10.16.120' TO 'mugunghwa_web'@'10.10.16.130'"
elif [ "$new" != 1 ]; then
    echo 'Reader account requires inspection; no password was changed.'; exit 1
fi
echo 'Game schema ready; Jetson reader restricted to 10.10.16.130. Existing data/passwords preserved.'
