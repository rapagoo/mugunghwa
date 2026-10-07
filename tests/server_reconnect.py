"""Isolated TCP regression: authenticated takeover, invalid login, split header."""
from pathlib import Path
import argparse
import socket
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--port', type=int, default=15002)
    args = parser.parse_args()
    connections = []
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, 'idpasswd.txt').write_text('PI PASSWD\nJETSON PASSWD\nSTM PASSWD\n')
        with open(Path(folder, 'server.log'), 'w') as log:
            server = subprocess.Popen([args.server, str(args.port)], cwd=folder, stdout=log, stderr=log)
        try:
            time.sleep(.3)
            def login(name, password='PASSWD', split=False):
                conn = socket.create_connection(('127.0.0.1', args.port), timeout=2)
                connections.append(conn)
                packet = ('['+name+':'+password+']').encode()
                if split:
                    conn.sendall(packet[:4]); time.sleep(.05); conn.sendall(packet[4:])
                else:
                    conn.sendall(packet)
                response = bytearray()
                while not response.endswith(b'\n'):
                    chunk = conn.recv(1)
                    assert chunk, response
                    response.extend(chunk)
                return conn, bytes(response)

            pi, reply = login('PI', split=True)
            assert b'New connected!' in reply
            jetson, _ = login('JETSON')
            for count in range(20):
                bad, reply = login('PI', 'WRONG')
                assert b'Authentication Error!' in reply
                assert bad.recv(1) == b''
                bad.close()
                jetson.sendall(b'[PI]TRIAL@READY\n')
                assert pi.recv(100) == b'[JETSON]TRIAL@READY\n'
                new_pi, reply = login('PI')
                assert b'New connected!' in reply
                assert pi.recv(1) == b''
                pi.close(); pi = new_pi
                pi.sendall(b'[JETSON]TRIAL@PING\n')
                assert jetson.recv(100) == b'[PI]TRIAL@PING\n'
                jetson.sendall(b'[PI]TRIAL@READY\n')
                assert pi.recv(100) == b'[JETSON]TRIAL@READY\n'
            print('PASS: split login, invalid-password isolation, 20 authenticated reconnects, bidirectional heartbeat')
        finally:
            for conn in connections:
                conn.close()
            server.terminate(); server.wait(timeout=5)


if __name__ == '__main__':
    main()
