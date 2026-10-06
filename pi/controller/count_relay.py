"""PI client for the COUNT communication test, not the game state machine."""
import argparse
from collections import deque
import re
import socket
import time


def parse_counts(payload, prefix):
    match = re.fullmatch(re.escape(prefix) + r'([0-9]{1,2})@([0-9]{1,2})@([0-9]{1,2})', payload)
    if not match:
        return None
    total, success, failure = map(int, match.groups())
    if success + failure > total:
        return None
    return total, success, failure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--target', choices=('STM', 'ARD'), action='append',
                        help='Repeat to select outputs; default is ARD and STM')
    args = parser.parse_args()
    targets = tuple(dict.fromkeys(args.target or ('ARD', 'STM')))
    pending = deque(maxlen=32)

    with socket.create_connection((args.host, args.port), timeout=5) as conn:
        conn.sendall(b'[PI:PASSWD]')
        stream = conn.makefile('rb')
        login = stream.readline(101)
        if len(login) > 100 or not login.endswith(b'\n') or b' New connected!' not in login:
            raise RuntimeError('PI login rejected or malformed')
        print(login.decode('ascii').strip(), flush=True)
        conn.settimeout(None)
        print('CONTROLLER_READY JETSON -> PI -> ' + ','.join(targets), flush=True)
        while True:
            raw = stream.readline(101)
            if not raw:
                raise RuntimeError('Server disconnected')
            if len(raw) > 100 or not raw.endswith(b'\n'):
                raise RuntimeError('Invalid or oversized TCP line')
            try:
                line = raw.decode('ascii').rstrip('\n')
            except UnicodeDecodeError:
                print('IGNORE non-ASCII message', flush=True)
                continue
            match = re.fullmatch(r'\[([A-Za-z0-9_]{1,9})\](.*)', line)
            if not match:
                print('IGNORE malformed message', flush=True)
                continue
            sender, payload = match.groups()
            now = time.monotonic()
            while pending and now - pending[0][0] > 30:
                pending.popleft()
            counts = parse_counts(payload, 'COUNT@')
            if sender == 'JETSON' and counts is not None:
                values = '@'.join(map(str, counts))
                for target in targets:
                    outgoing = '[' + target + ']COUNT@' + values + '\n'
                    conn.sendall(outgoing.encode('ascii'))
                    pending.append((now, target, counts))
                    print('RX ' + line + ' -> TX ' + outgoing.strip(), flush=True)
                continue
            counts = parse_counts(payload, 'APPLIED@COUNT@')
            if sender in targets and counts is not None:
                entry = next((item for item in pending if item[1] == sender and item[2] == counts), None)
                if entry is not None:
                    pending.remove(entry)
                    outgoing = '[JETSON]APPLIED@COUNT@' + '@'.join(map(str, counts)) + '\n'
                    conn.sendall(outgoing.encode('ascii'))
                    print('RX ' + line + ' -> TX ' + outgoing.strip(), flush=True)
                    continue
            print('IGNORE ' + line, flush=True)


if __name__ == '__main__':
    main()
