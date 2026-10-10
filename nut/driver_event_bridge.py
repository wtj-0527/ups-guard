"""Forward NUT's native driver socket updates; never issue UPS write commands."""
import glob
import json
import os
import queue
import shlex
import socket
import stat
import threading
import time
import urllib.request

OUT = queue.Queue(maxsize=512)
SECRET = os.environ.get('NUT_EVENT_SECRET', '')
MIN_SECRET_LENGTH = 16
URL = os.environ.get('NUT_EVENT_URL', 'http://backend:8000/api/system/driver-event')


def publish(values, healthy, reason):
    frame = {'variables': dict(values), 'healthy': healthy, 'reason': reason,
             'created_at': time.time()}
    # Never block the driver socket reader on a slow/unavailable backend:
    # when the queue is full, drop the oldest frame (it would expire anyway).
    while True:
        try:
            OUT.put_nowait(frame)
            return
        except queue.Full:
            try:
                OUT.get_nowait()
                OUT.task_done()
            except queue.Empty:
                pass


def deliver():
    while True:
        frame = OUT.get()
        while True:
            # Never replay an old power state after a backend outage.
            if time.time() - frame['created_at'] > 25:
                break
            try:
                req = urllib.request.Request(URL, data=json.dumps(frame).encode(),
                    headers={'X-NUT-Event-Secret': SECRET,
                             'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, timeout=3) as response:
                    assert response.status == 200
                break
            except Exception as exc:
                print('Event delivery retry: ' + type(exc).__name__, flush=True)
                time.sleep(2)
        OUT.task_done()


def find_socket():
    explicit = os.environ.get('NUT_DRIVER_SOCKET')
    if explicit:
        if not stat.S_ISSOCK(os.stat(explicit).st_mode):
            raise RuntimeError('NUT_DRIVER_SOCKET is not a Unix socket')
        return explicit
    paths = [p for p in glob.glob('/var/run/nut/*') if stat.S_ISSOCK(os.stat(p).st_mode)]
    if len(paths) != 1:
        raise RuntimeError('Expected exactly one UPS driver socket')
    return paths[0]


def watch(path):
    values = {}
    ready = False
    healthy = False
    buffer = b''
    last_rx = last_ping = last_heartbeat = time.monotonic()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.connect(path)
        conn.settimeout(1)
        conn.sendall(b'DUMPALL\n')
        print('Native driver event stream connected', flush=True)
        while True:
            changed = False
            try:
                chunk = conn.recv(65536)
                if not chunk:
                    raise ConnectionError('Driver stream closed')
                buffer += chunk
                if len(buffer) > 1048576:
                    raise ValueError('Driver frame too large')
                last_rx = time.monotonic()
                while b'\n' in buffer:
                    raw, buffer = buffer.split(b'\n', 1)
                    try:
                        parts = shlex.split(raw.decode('utf-8'), comments=False)
                    except (UnicodeDecodeError, ValueError):
                        # One malformed line must not tear down the stream.
                        print('Skipping malformed driver line', flush=True)
                        continue
                    if not parts:
                        continue
                    command = parts[0]
                    if command == 'SETINFO' and len(parts) >= 3:
                        key, value = parts[1], parts[2]
                        different = values.get(key) != value
                        values[key] = value
                        if different and not key.startswith('driver.'):
                            changed = True
                            # Preserve critical transitions even in a batched recv.
                            if ready and key == 'ups.status':
                                publish(values, healthy, 'STATUS')
                    elif command == 'DELINFO' and len(parts) == 2:
                        values.pop(parts[1], None)
                        changed = True
                    elif command == 'DUMPDONE':
                        ready = True
                        changed = True
                    elif command in ('DATAOK', 'DATASTALE'):
                        healthy = command == 'DATAOK'
                        changed = True
                if ready and changed:
                    publish(values, healthy, 'UPDATE')
            except socket.timeout:
                pass
            now = time.monotonic()
            if now - last_rx > 35:
                raise TimeoutError('Driver heartbeat lost')
            if now - last_ping >= 10:
                conn.sendall(b'PING\n')
                last_ping = now
            if ready and now - last_heartbeat >= 15:
                publish(values, healthy, 'HEARTBEAT')
                last_heartbeat = now


def main():
    if len(SECRET) < MIN_SECRET_LENGTH:
        raise RuntimeError('NUT_EVENT_SECRET (>= 16 chars) is required for the driver event bridge')
    threading.Thread(target=deliver, daemon=True).start()
    announced_down = False
    while True:
        try:
            path = find_socket()
        except Exception as exc:
            # Driver socket not created yet (startup) or ambiguous: report the
            # outage once instead of posting DISCONNECTED every retry.
            if not announced_down:
                print('Waiting for driver socket: ' + str(exc), flush=True)
                publish({}, False, 'DISCONNECTED')
                announced_down = True
            time.sleep(2)
            continue
        try:
            announced_down = False
            watch(path)
        except Exception as exc:
            print('Native driver event stream reconnect: ' + type(exc).__name__, flush=True)
            publish({}, False, 'DISCONNECTED')
            announced_down = True
            time.sleep(2)


if __name__ == '__main__':
    main()
