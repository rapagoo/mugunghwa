"""Run on Pi: isolated server, PI controller, MCU simulators, Python sender."""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


def login(port, name):
    conn = socket.create_connection(('127.0.0.1', port), timeout=3)
    conn.sendall(('[' + name + ':PASSWD]').encode())
    stream = conn.makefile('rb')
    assert b' New connected!' in stream.readline()
    return conn, stream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=15000)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mugunghwa-integration-') as folder:
        Path(folder, 'idpasswd.txt').write_text('PI PASSWD\nJETSON PASSWD\nSTM PASSWD\nARD PASSWD\n')
        server = controller = sender = None
        try:
            with open(Path(folder, 'server.log'), 'w') as log:
                server = subprocess.Popen([str(args.root / 'pi/server/iot_server'), str(args.port)],
                                          cwd=folder, stdout=log, stderr=log)
            time.sleep(0.3)
            controller = subprocess.Popen([sys.executable, '-u', str(args.root / 'pi/controller/count_relay.py'),
                                           '--port', str(args.port)], stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True)
            assert ' New connected!' in controller.stdout.readline()
            assert 'CONTROLLER_READY' in controller.stdout.readline()
            stm, stm_stream = login(args.port, 'STM')
            ard, ard_stream = login(args.port, 'ARD')
            jetson, jetson_stream = login(args.port, 'JETSON')
            with stm, ard, jetson:
                jetson.sendall(b'[PI]COUNT@1@2@0\n')
                for conn in (stm, ard):
                    conn.settimeout(0.2)
                    try:
                        raise AssertionError('Invalid COUNT reached MCU: ' + repr(conn.recv(1)))
                    except socket.timeout:
                        pass
                    conn.settimeout(3)
                jetson.sendall(b'[PI]COUNT@4@')
                time.sleep(0.1)
                jetson.sendall(b'2@1\n')
                for name, conn, stream in (('STM', stm, stm_stream), ('ARD', ard, ard_stream)):
                    message = stream.readline()
                    assert message == b'[PI]COUNT@4@2@1\n', message
                    print(name + '_RX', message.decode().strip(), flush=True)
                    conn.sendall(b'[PI]APPLIED@COUNT@4@2@1\n')
                    assert jetson_stream.readline() == b'[PI]APPLIED@COUNT@4@2@1\n'
                jetson.sendall(b'[PI]COUNT@1@0@0\n[PI]COUNT@2@1@0\n')
                for stream in (stm_stream, ard_stream):
                    assert stream.readline() == b'[PI]COUNT@1@0@0\n'
                    assert stream.readline() == b'[PI]COUNT@2@1@0\n'
                jetson.close()
                jetson_stream.close()
                time.sleep(0.3)
                sender = subprocess.Popen([sys.executable, '-u', str(args.root / 'jetson/count_test_client.py'),
                                           '--host', '127.0.0.1', '--port', str(args.port), '--cycles', '1'],
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for conn, stream in ((stm, stm_stream), (ard, ard_stream)):
                    assert stream.readline() == b'[PI]COUNT@1@0@0\n'
                    conn.sendall(b'[PI]APPLIED@COUNT@1@0@0\n')
                output, _ = sender.communicate(timeout=6)
                assert sender.returncode == 0, output
                assert output.count('RX: [PI]APPLIED@COUNT@1@0@0') == 2, output
                print(output, end='')
                print('PASS: Python sender, PI controller, both MCU replies, invalid/split/batch frames')
        finally:
            for proc in (sender, controller, server):
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)


if __name__ == '__main__':
    main()
