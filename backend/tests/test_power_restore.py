"""Regression coverage without physical UPS, notifications or shutdown calls."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from models import EventType, UpsData, UpsStatus
from services.monitor import UpsMonitor
from services.voltage_quality import assess_voltage_quality


class PowerRestoreTests(unittest.IsolatedAsyncioTestCase):
    def data(self, status):
        return UpsData(status=status, battery_charge=60, battery_runtime=900,
                       input_voltage=222, last_update=datetime.now())

    async def asyncSetUp(self):
        self.history = SimpleNamespace(add_event=AsyncMock())
        self.notifier = SimpleNamespace(notify=AsyncMock())
        manager = SimpleNamespace(get_config=AsyncMock(return_value=
            SimpleNamespace(wol_on_power_restore=False)))
        for target, replacement in [
            ('services.monitor.get_history_service', AsyncMock(return_value=self.history)),
            ('services.monitor.get_notifier_service', lambda: self.notifier),
            ('config.get_config_manager', AsyncMock(return_value=manager)),
        ]:
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def monitor(self):
        monitor = UpsMonitor(None, None)
        monitor._handle_status = AsyncMock()
        monitor._sample_metrics = AsyncMock()
        return monitor

    async def test_zero_voltage_keeps_battery_telemetry(self):
        for flags, expected in [('OB', UpsStatus.ON_BATTERY),
                                ('OB LB', UpsStatus.LOW_BATTERY)]:
            with self.subTest(flags=flags):
                variables = {'ups.status': flags, 'input.voltage': '0',
                             'input.voltage.nominal': '220', 'input.transfer.low': '160',
                             'input.transfer.high': '278', 'battery.charge': '60'}
                monitor = UpsMonitor(SimpleNamespace(
                    list_vars=AsyncMock(return_value=variables)), None)
                data = await monitor._read_ups_data()
                self.assertIsNotNone(data)
                self.assertEqual(data.status, expected)
                self.assertEqual(data.input_voltage, 0)

    def test_nonpositive_voltage_skips_optional_score(self):
        for actual, nominal in [(0, 220), (-1, 220), (222, 0), (222, -1)]:
            with self.subTest(actual=actual, nominal=nominal):
                self.assertIsNone(assess_voltage_quality(
                    actual, nominal, None, None, 160, 278, ['OL']))
        self.assertIsNotNone(assess_voltage_quality(
            222, 220, None, None, 160, 278, ['OL']))

    async def test_power_transitions_survive_connectivity_loss(self):
        OL, OB, LB, OFF = (UpsStatus.ONLINE, UpsStatus.ON_BATTERY,
                           UpsStatus.LOW_BATTERY, UpsStatus.OFFLINE)
        lost, restored = EventType.POWER_LOST, EventType.POWER_RESTORED
        for sequence, expected in [
            ([OL, OB, OL, OL], [lost, restored]),
            ([OL, OB, OFF, OL], [lost, restored]),
            ([OL, LB, OFF, OL], [EventType.LOW_BATTERY, restored]),
            ([OL, OFF, OL], []),
            ([OL, OFF, OB], [lost]),
            ([OL, OB, OFF, OB, OL], [lost, restored]),
        ]:
            with self.subTest(sequence=sequence):
                monitor = self.monitor()
                self.notifier.notify.reset_mock()
                self.history.add_event.reset_mock()
                for status in sequence:
                    await monitor._process_ups_data(self.data(status))
                self.assertEqual([c.args[0] for c in
                    self.notifier.notify.await_args_list], expected)
                self.assertEqual([c.args[0] for c in
                    self.history.add_event.await_args_list], expected)

    async def test_startup_on_battery_remembers_power_state(self):
        monitor = self.monitor()
        monitor._read_ups_data = AsyncMock(return_value=self.data(UpsStatus.ON_BATTERY))
        await monitor._check_initial_status()
        await monitor._process_ups_data(self.data(UpsStatus.OFFLINE))
        await monitor._process_ups_data(self.data(UpsStatus.ONLINE))
        self.assertEqual([c.args[0] for c in self.notifier.notify.await_args_list],
                         [EventType.POWER_LOST, EventType.POWER_RESTORED])


if __name__ == '__main__':
    unittest.main()
