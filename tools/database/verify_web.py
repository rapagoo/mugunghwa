"""Jetson live DB verification: read succeeds, write permission denied."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'jetson'))
from game.mariadb_store import MariaGameDatabase

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='.runtime/db/web.json')
    args=parser.parse_args()
    database=MariaGameDatabase(args.config)
    state=database.snapshot()
    connection=database.driver.connect(**database.config,charset='utf8mb4',autocommit=False)
    try:
        with connection.cursor() as cursor:
            try:
                # Valid statement that affects no rows; must still require UPDATE privilege.
                cursor.execute("UPDATE games SET phase=phase WHERE id='__permission_probe__'")
            except database.driver.MySQLError as error:
                if error.args[0] != 1142:
                    raise RuntimeError('Unexpected permission probe failure') from None
            else:
                raise RuntimeError('Web account unexpectedly permits writes')
        print('MariaDB SELECT verified; UPDATE denied. Game present: '+str(state['game'] is not None))
    finally:
        connection.rollback()
        connection.close()

if __name__=='__main__':
    main()
