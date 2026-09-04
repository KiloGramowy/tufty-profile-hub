import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

import safe_wifi


class FakeWLAN:
    def __init__(self, connected=False, status_value=0, connect_error=None):
        self.connected = connected
        self.status_value = status_value
        self.connect_error = connect_error
        self.connect_calls = []
        self.active_calls = []
        self.disconnect_calls = 0

    def active(self, value):
        self.active_calls.append(value)

    def isconnected(self):
        return self.connected

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        if self.connect_error:
            raise self.connect_error

    def status(self):
        return self.status_value

    def disconnect(self):
        self.disconnect_calls += 1


class FakeNetwork:
    STA_IF = object()

    def __init__(self, wlan):
        self.wlan = wlan

    def WLAN(self, interface):
        self.interface = interface
        return self.wlan


class SafeWifiTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(safe_wifi)
        self.now = [1000]
        safe_wifi.time = SimpleNamespace(
            ticks_ms=lambda: self.now[0],
            ticks_diff=lambda now, then: now - then,
        )

    def configure(self, wlan, ssid="Home WiFi", password="secret"):
        safe_wifi.network = FakeNetwork(wlan)
        safe_wifi.secrets = SimpleNamespace(WIFI_SSID=ssid, WIFI_PASSWORD=password)

    def test_missing_credentials_returns_false_without_exception(self):
        self.configure(FakeWLAN(), ssid="", password="")
        self.assertIs(safe_wifi.connect(), False)

    def test_first_wifi_attempt_starts_non_blocking_and_returns_none(self):
        wlan = FakeWLAN()
        self.configure(wlan)

        self.assertIsNone(safe_wifi.connect())
        self.assertEqual(wlan.connect_calls, [("Home WiFi", "secret")])

    def test_connected_returns_true(self):
        wlan = FakeWLAN(connected=True)
        self.configure(wlan)

        self.assertIs(safe_wifi.connect(), True)
        self.assertEqual(wlan.connect_calls, [])

    def test_ap_failure_returns_false_without_fatal_path(self):
        wlan = FakeWLAN(status_value=-2)
        self.configure(wlan)

        self.assertIsNone(safe_wifi.connect())
        self.assertIs(safe_wifi.connect(), False)
        self.assertEqual(wlan.disconnect_calls, 1)

    def test_timeout_returns_false_without_fatal_path(self):
        wlan = FakeWLAN()
        self.configure(wlan)

        self.assertIsNone(safe_wifi.connect())
        self.now[0] += safe_wifi.CONNECT_TIMEOUT_MS
        self.assertIs(safe_wifi.connect(), False)

    def test_retry_cooldown_bounds_failed_state(self):
        wlan = FakeWLAN(connect_error=OSError("join failed"))
        self.configure(wlan)

        self.assertIs(safe_wifi.connect(), False)
        self.assertIs(safe_wifi.connect(), False)
        self.assertEqual(wlan.connect_calls, [("Home WiFi", "secret")])

        self.now[0] += safe_wifi.RETRY_COOLDOWN_MS
        self.assertIs(safe_wifi.connect(), False)
        self.assertEqual(
            wlan.connect_calls,
            [("Home WiFi", "secret"), ("Home WiFi", "secret")],
        )

    def test_runtime_avoids_fatal_paths_and_system_wifi_helper(self):
        for path in (ROOT / "profile_hub").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("fatal_error(", text)
            self.assertNotIn("machine.reset(", text)
            self.assertNotIn("wifi.connect(", text)


if __name__ == "__main__":
    unittest.main()
