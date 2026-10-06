"""Send dummy COUNT values only to PI; camera data is not used here."""
import argparse
import select
import socket
import time

COUNTS = ((1, 0, 0), (2, 1, 0), (3, 1, 1), (4, 2, 1), (3, 1, 1), (2, 1, 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='10.10.16.90')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--cycles', type=int, help='Number of messages; default repeats forever')
    args = parser.parse_args()
    if args.cycles is not None and args.cycles <= 0:
        parser.error('cycles must be positive')
    with socket.create_connection((args.host, args.port), timeout=5) as conn:
        conn.sendall(b'[JETSON:PASSWD]')
        login = bytearray()
        while not login.endswith(b'\n'):
            part = conn.recv(1)
            if not part or len(login) >= 100:
                raise RuntimeError('Login reply failed or too long')
            login.extend(part)
        if b' New connected!' not in login:
            raise RuntimeError('JETSON login rejected: ' + login.decode('ascii', errors='replace'))
        print(login.decode('ascii').strip(), flush=True)
        print('Sending dummy COUNT only to PI every 3 seconds', flush=True)
        conn.settimeout(None)
        next_send = time.monotonic()
        sent = 0
        buffered = bytearray()
        while True:
            now = time.monotonic()
            if now >= next_send:
                if args.cycles is not None and sent >= args.cycles:
                    return
                values = '@'.join(map(str, COUNTS[sent % len(COUNTS)]))
                message = '[PI]COUNT@' + values + '\n'
                conn.sendall(message.encode('ascii'))
                print('TX: ' + message.strip(), flush=True)
                sent += 1
                next_send = time.monotonic() + 3
            readable, _, _ = select.select([conn], [], [], max(0, next_send - time.monotonic()))
            if readable:
                chunk = conn.recv(256)
                if not chunk:
                    raise RuntimeError('Server disconnected')
                buffered.extend(chunk)
                while b'\n' in buffered:
                    line, _, rest = buffered.partition(b'\n')
                    if len(line) >= 100:
                        raise RuntimeError('Response line too long')
                    print('RX: ' + line.decode('ascii', errors='replace'), flush=True)
                    buffered = bytearray(rest)
                if len(buffered) >= 100:
                    raise RuntimeError('Unterminated response too long')


if __name__ == '__main__':
    main()
