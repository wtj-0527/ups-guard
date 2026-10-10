"""Driver event ingress: dedicated secret auth and monitor state updates.

No physical UPS, notifications, or shutdown operations are involved.
"""
import asyncio
import time
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import driver_events
from middleware.auth import AuthMiddleware
from services.monitor import UpsMonitor

SECRET = 'bridge-secret-0123456789'
API_TOKEN = 'api-token-abcdef'


def make_monitor():
    monitor = UpsMonitor.__new__(UpsMonitor)
    monitor.config = SimpleNamespace(event_driven_enabled=True, monitoring_mode='event_driven',
                                     event_driven_fallback=True)
    monitor._driver_bridge_data = {}
    monitor._driver_bridge_seen = 0.0
    monitor._driver_bridge_frames = 0
    monitor._driver_bridge_seq = 0
    monitor._driver_bridge_consumed_seq = 0
    monitor._driver_bridge_statuses = deque(maxlen=512)
    monitor._driver_bridge_wakeup = asyncio.Event()
    monitor._event_mode_active = False
    return monitor


def frame(**overrides):
    body = {'variables': {'ups.status': 'OB'}, 'healthy': True, 'reason': 'STATUS',
            'created_at': time.time()}
    body.update(overrides)
    return body


class IngressTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.middleware('http')(AuthMiddleware(app, API_TOKEN))
        app.include_router(driver_events.router, prefix='/api')
        self.client = TestClient(app)
        self.monitor = make_monitor()
        env = {'NUT_EVENT_BRIDGE': 'true', 'NUT_EVENT_SECRET': SECRET}
        patches = [patch.dict('os.environ', env),
                   patch.object(driver_events, 'get_monitor', return_value=self.monitor)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def post(self, body, headers=None):
        return self.client.post('/api/system/driver-event', json=body, headers=headers or {})

    def test_valid_secret_accepted(self):
        response = self.post(frame(), {'X-NUT-Event-Secret': SECRET})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['event_mode_active'])
        self.assertEqual(self.monitor._driver_bridge_data['ups.status'], 'OB')
        self.assertEqual(len(self.monitor._driver_bridge_statuses), 1)

    def test_api_token_is_not_accepted(self):
        response = self.post(frame(), {'Authorization': 'Bearer ' + API_TOKEN})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.monitor._driver_bridge_frames, 0)

    def test_wrong_or_missing_secret_rejected(self):
        self.assertEqual(self.post(frame(), {'X-NUT-Event-Secret': 'x' * 24}).status_code, 401)
        self.assertEqual(self.post(frame()).status_code, 401)
        self.assertEqual(self.monitor._driver_bridge_frames, 0)

    def test_short_secret_disables_ingress(self):
        with patch.dict('os.environ', {'NUT_EVENT_SECRET': 'short'}):
            response = self.post(frame(), {'X-NUT-Event-Secret': 'short'})
        self.assertEqual(response.status_code, 503)

    def test_bridge_disabled_returns_404(self):
        with patch.dict('os.environ', {'NUT_EVENT_BRIDGE': 'false'}):
            response = self.post(frame(), {'X-NUT-Event-Secret': SECRET})
        self.assertEqual(response.status_code, 404)

    def test_expired_frame_rejected(self):
        response = self.post(frame(created_at=time.time() - 60), {'X-NUT-Event-Secret': SECRET})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.monitor._driver_bridge_frames, 0)

    def test_other_api_routes_still_require_token(self):
        response = self.client.get('/api/system/monitoring-stats')
        self.assertEqual(response.status_code, 401)


class IngestFrameTests(unittest.TestCase):
    def setUp(self):
        self.monitor = make_monitor()
        env = patch.dict('os.environ', {'NUT_EVENT_BRIDGE': 'true'})
        env.start()
        self.addCleanup(env.stop)

    def test_heartbeat_does_not_advance_sequence(self):
        self.monitor.ingest_driver_frame({'ups.status': 'OL'}, True, 'UPDATE')
        self.monitor.ingest_driver_frame({'ups.status': 'OL'}, True, 'HEARTBEAT')
        self.assertEqual(self.monitor._driver_bridge_seq, 1)
        self.assertEqual(self.monitor._driver_bridge_frames, 2)

    def test_unhealthy_frame_clears_state(self):
        self.monitor.ingest_driver_frame({'ups.status': 'OB'}, True, 'STATUS')
        self.assertFalse(self.monitor.ingest_driver_frame({}, False, 'DISCONNECTED'))
        self.assertEqual(self.monitor._driver_bridge_data, {})
        self.assertFalse(self.monitor._driver_bridge_statuses)

    def test_bridge_age_is_none_before_first_frame(self):
        self.assertIsNone(self.monitor.driver_bridge_age_seconds())
        self.monitor.ingest_driver_frame({'ups.status': 'OL'}, True, 'UPDATE')
        self.assertLess(self.monitor.driver_bridge_age_seconds(), 1)

    def test_polling_mode_disables_bridge(self):
        self.monitor.config.monitoring_mode = 'polling'
        self.assertFalse(self.monitor._bridge_active())
        self.assertFalse(self.monitor.ingest_driver_frame({'ups.status': 'OL'}, True, 'UPDATE'))


if __name__ == '__main__':
    unittest.main()
