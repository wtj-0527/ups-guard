"""Exercise the real configuration and monitor code without accessing any UPS."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "nut/entrypoint.sh").read_text()
CONFIG_PHASE = SOURCE.split("# 生成 upsd.conf", 1)[0]
MONITOR = "monitor_ups_driver() {" + SOURCE.split(
    "monitor_ups_driver() {", 1
)[1].split("# 在后台启动 UPS 驱动监控", 1)[0]
USB_SCAN = """
[nutdev1]
    driver = "usbhid-ups"
    port = "auto"
    vendorid = "051d"
    productid = "0002"
    serial = "TEST1234"
"""


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        temp = ROOT / "tmp"
        temp.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temp)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.nut = self.root / "nut"
        self.nut.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls"
        self.env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "UPS_NAME": "ups",
            "CALLS": str(self.calls),
            "COUNTER": str(self.root / "counter"),
            "STOP_AFTER": "7",
            "SCAN_RESULT_FIXTURE": "",
        }
        self.command("nut-scanner", """
printf 'scan\\n' >> "$CALLS"
printf '%s' "$SCAN_RESULT_FIXTURE"
""")

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def run_phase(self, monitor=False, **env):
        script = CONFIG_PHASE.replace(
            "/etc/nut", str(self.nut)
        ).replace("/tmp/ups-info", str(self.root / "ups-info"))
        if monitor:
            script += "\n" + MONITOR + "\nmonitor_ups_driver\n"
        return subprocess.run(
            ["bash", "-c", script], env=dict(self.env, **env),
            text=True, capture_output=True, timeout=10,
        )

    def config(self):
        return (self.nut / "ups.conf").read_text()

    def test_usb_without_device_still_uses_dummy(self):
        result = self.run_phase()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("driver = dummy-ups", self.config())
        self.assertTrue((self.nut / "dummy.dev").is_file())
        self.assertEqual(self.calls.read_text(), "scan\n")

    def test_usb_discovery_still_configures_detected_device(self):
        result = self.run_phase(SCAN_RESULT_FIXTURE=USB_SCAN)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("driver = usbhid-ups", self.config())
        self.assertIn("subdriver = apc", self.config())
        self.assertNotIn("protocol =", self.config())

    def test_serial_path_preserves_driver_and_protocol_without_usb_scan(self):
        result = self.run_phase(
            UPS_DRIVER="nutdrv_qx", UPS_PORT="/dev/ttyUSB0",
            UPS_PROTOCOL="ablerex", SCAN_RESULT_FIXTURE=USB_SCAN,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.config()
        self.assertIn("driver = nutdrv_qx", config)
        self.assertIn("port = /dev/ttyUSB0", config)
        self.assertIn("protocol = ablerex", config)
        self.assertIn("runtimecal = 300,100,2400,50", config)
        self.assertNotIn("[INFO]", config)
        self.assertNotIn("vendorid =", config)
        self.assertFalse(self.calls.exists())

    def test_explicit_manual_mode_also_preserves_auto_port(self):
        result = self.run_phase(
            UPS_AUTO_DETECT="false", UPS_DRIVER="nutdrv_qx",
            UPS_PROTOCOL="ablerex", SCAN_RESULT_FIXTURE=USB_SCAN,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("driver = nutdrv_qx", self.config())
        self.assertIn("port = auto", self.config())
        self.assertFalse(self.calls.exists())

    def test_identity_overrides_are_optional_and_persist_on_regeneration(self):
        for _ in range(2):
            result = self.run_phase(
                UPS_DRIVER="nutdrv_qx", UPS_PORT="/dev/ttyUSB0",
                UPS_MFR="VISENCH", UPS_MODEL="C3K",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for prefix in ("device", "ups"):
                self.assertIn(f'override.{prefix}.mfr = "VISENCH"', self.config())
                self.assertIn(f'override.{prefix}.model = "C3K"', self.config())
        result = self.run_phase(UPS_DRIVER="nutdrv_qx", UPS_PORT="/dev/ttyUSB0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("override.device.", self.config())

    def test_identity_text_is_escaped_and_cannot_inject_configuration(self):
        result = self.run_phase(
            UPS_DRIVER="nutdrv_qx", UPS_PORT="/dev/ttyUSB0",
            UPS_MFR='威神 "UPS" \\ Lab', UPS_MODEL="C3K #1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('override.device.mfr = "威神 \\"UPS\\" \\\\ Lab"', self.config())
        self.assertIn('override.device.model = "C3K #1"', self.config())
        for key in ("UPS_MFR", "UPS_MODEL"):
            result = self.run_phase(**{key: "bad\n    driver = dummy-ups"})
            self.assertNotEqual(result.returncode, 0)

    def test_identity_overrides_do_not_hide_dummy_mode(self):
        result = self.run_phase(UPS_MFR="VISENCH", UPS_MODEL="C3K")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("driver = dummy-ups", self.config())
        self.assertNotIn("override.device.", self.config())
        self.assertNotIn("override.ups.", self.config())

    def test_rejects_protocol_configuration_injection(self):
        result = self.run_phase(UPS_PROTOCOL="ablerex\n    driver = dummy-ups")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.nut / "ups.conf").exists())

    def test_rejects_invalid_discovery_mode(self):
        result = self.run_phase(UPS_AUTO_DETECT="flase")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.nut / "ups.conf").exists())

    def test_manual_reconnect_does_not_scan_or_replace_configuration(self):
        self.command("upsc", "exit 1\n")
        self.command("timeout", 'shift\nexec "$@"\n')
        self.command("upsdrvctl", """
printf '%s\\n' "$1" >> "$CALLS"
[ "$1" != start ]
""")
        # End after three failed reconnect attempts instead of looping forever.
        self.command("sleep", """
count=$(cat "$COUNTER" 2>/dev/null || printf 0)
count=$((count + 1))
printf '%s' "$count" > "$COUNTER"
[ "$count" -lt "$STOP_AFTER" ] || exit 77
""")
        result = self.run_phase(
            monitor=True, UPS_DRIVER="nutdrv_qx",
            UPS_PORT="/dev/ttyUSB0", UPS_PROTOCOL="ablerex",
            UPS_MFR="VISENCH", UPS_MODEL="C3K",
        )
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertEqual(self.calls.read_text(), "stop\nstart\n" * 3)
        self.assertIn("driver = nutdrv_qx", self.config())
        self.assertIn("port = /dev/ttyUSB0", self.config())
        self.assertIn("protocol = ablerex", self.config())
        self.assertNotIn("dummy-ups", self.config())
        self.assertIn('override.device.mfr = "VISENCH"', self.config())
        self.assertIn('override.device.model = "C3K"', self.config())


if __name__ == "__main__":
    unittest.main()
