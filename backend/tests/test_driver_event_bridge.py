"""Native socket fixtures: no real UPS, HTTP delivery, or shutdown commands."""
import importlib.util
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[2] / 'nut' / 'driver_event_bridge.py'
spec = importlib.util.spec_from_file_location('driver_event_bridge', path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


@unittest.skipUnless(hasattr(socket, 'AF_UNIX'), 'Unix sockets required')
class DriverSocketTests(unittest.TestCase):
    def test_initial_snapshot_power_edges_stale_and_disconnect(self):
        frames = []
        commands = []
        with tempfile.TemporaryDirectory() as directory:
            address = str(Path(directory) / 'driver')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(address)
                server.listen()

                def send_fixture():
                    with server.accept()[0] as connection:
                        commands.append(connection.recv(64))
                        connection.sendall(
                            b'SETINFO ups.status "OL"\n'
                            b'SETINFO ups.model "Fixture UPS"\n'
                            b'DATAOK\nDUMPDONE\n'
                            b'SETINFO ups.broken "unterminated\n'
                            b'SETINFO ups.bad "\xff\xfe"\n'
                            b'SETINFO ups.status "OB"\n'
                            b'SETINFO ups.status "OL"\nDATASTALE\n')

                worker = threading.Thread(target=send_fixture)
                worker.start()
                with patch.object(bridge, 'publish',
                        side_effect=lambda values, healthy, reason:
                        frames.append((dict(values), healthy, reason))):
                    with self.assertRaises(ConnectionError):
                        bridge.watch(address)
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive())
        self.assertEqual(commands, [b'DUMPALL\n'])
        edges = [values['ups.status'] for values, healthy, reason in frames if reason == 'STATUS']
        self.assertEqual(edges, ['OB', 'OL'])
        self.assertTrue(frames[0][1])
        self.assertFalse(frames[-1][1])
        self.assertEqual(frames[-1][0]['ups.model'], 'Fixture UPS')
        # Malformed lines are skipped without tearing down the stream.
        self.assertNotIn('ups.broken', frames[-1][0])


class PublishTests(unittest.TestCase):
    def test_full_queue_drops_oldest_without_blocking(self):
        with patch.object(bridge, 'OUT', bridge.queue.Queue(maxsize=2)):
            for index in range(5):
                bridge.publish({'n': str(index)}, True, 'UPDATE')
            kept = [bridge.OUT.get_nowait()['variables']['n'] for _ in range(2)]
        self.assertEqual(kept, ['3', '4'])


if __name__ == '__main__':
    unittest.main()
