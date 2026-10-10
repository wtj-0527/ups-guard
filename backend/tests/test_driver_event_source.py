"""No physical UPS, notifications, credentials, or shutdown operations."""
import time
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock
from services.driver_event_source import read_driver_variables


class EventSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = SimpleNamespace(list_vars=AsyncMock(return_value={'ups.status': 'OL'}))
        self.monitor = SimpleNamespace(
            config=SimpleNamespace(event_driven_fallback=True), nut_client=self.client,
            _driver_bridge_seen=time.monotonic(), _driver_bridge_data={'ups.status': 'OL'},
            _driver_bridge_statuses=deque(), _event_mode_active=False,
            _driver_bridge_seq=1, _driver_bridge_consumed_seq=0)

    async def read(self):
        return (await read_driver_variables(self.monitor))[0]

    async def test_healthy_events_do_not_poll(self):
        self.assertEqual(await self.read(), {'ups.status': 'OL'})
        self.assertTrue(self.monitor._event_mode_active)
        self.client.list_vars.assert_not_awaited()

    async def test_expired_stream_polls_and_recovers(self):
        self.monitor._driver_bridge_seen -= 36
        self.assertEqual(await self.read(), {'ups.status': 'OL'})
        self.assertFalse(self.monitor._event_mode_active)
        self.client.list_vars.assert_awaited_once()
        self.monitor._driver_bridge_seen = time.monotonic()
        self.monitor._driver_bridge_data = {'ups.status': 'OB'}
        self.assertEqual(await self.read(), {'ups.status': 'OB'})
        self.assertTrue(self.monitor._event_mode_active)
        self.client.list_vars.assert_awaited_once()

    async def test_unhealthy_stream_polls_immediately(self):
        self.monitor._driver_bridge_data = {}
        await self.read()
        self.client.list_vars.assert_awaited_once()
        self.assertFalse(self.monitor._event_mode_active)

    async def test_disabled_fallback_never_polls(self):
        self.monitor.config.event_driven_fallback = False
        self.monitor._driver_bridge_seen -= 36
        self.assertEqual(await self.read(), {})
        self.client.list_vars.assert_not_awaited()

    async def test_failed_poll_does_not_reuse_stale_data(self):
        self.monitor._driver_bridge_seen -= 36
        self.client.list_vars.side_effect = ConnectionError('UPS unavailable')
        with self.assertRaises(ConnectionError):
            await self.read()
        self.assertFalse(self.monitor._event_mode_active)

    async def test_status_edges_preserve_order(self):
        now = time.monotonic()
        self.monitor._driver_bridge_statuses.extend([
            (now, {'ups.status': 'OB'}), (now, {'ups.status': 'OL'})])
        self.assertEqual((await self.read())['ups.status'], 'OB')
        self.assertEqual((await self.read())['ups.status'], 'OL')
        self.client.list_vars.assert_not_awaited()

    async def test_expired_edges_are_discarded(self):
        self.monitor._driver_bridge_statuses.append((time.monotonic() - 26, {'ups.status': 'OB'}))
        self.assertEqual((await self.read())['ups.status'], 'OL')
        self.assertFalse(self.monitor._driver_bridge_statuses)

    async def test_cached_snapshot_is_reported_as_cache(self):
        _, source = await read_driver_variables(self.monitor)
        self.assertEqual(source, 'event')
        _, source = await read_driver_variables(self.monitor)
        self.assertEqual(source, 'cache')
        self.monitor._driver_bridge_seq += 1
        _, source = await read_driver_variables(self.monitor)
        self.assertEqual(source, 'event')

    async def test_fallback_poll_is_reported_as_poll(self):
        self.monitor._driver_bridge_seen -= 36
        _, source = await read_driver_variables(self.monitor)
        self.assertEqual(source, 'poll')


if __name__ == '__main__':
    unittest.main()
