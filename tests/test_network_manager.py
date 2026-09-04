import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

from network_manager import NetworkManager, select_configured_network


class FakeWLAN:
    def __init__(
        self,
        scans,
        connected=False,
        active_error=None,
        isconnected_error=None,
        scan_error=None,
        connect_error=None,
    ):
        self.scans = scans
        self.connected = connected
        self.active_error = active_error
        self.isconnected_error = isconnected_error
        self.scan_error = scan_error
        self.connect_error = connect_error
        self.connect_calls = []

    def active(self, value):
        if self.active_error:
            raise self.active_error
        self.active_value = value

    def isconnected(self):
        if self.isconnected_error:
            raise self.isconnected_error
        return self.connected

    def scan(self):
        if self.scan_error:
            raise self.scan_error
        return self.scans

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        if self.connect_error:
            raise self.connect_error
        self.connected = True


class NeverConnectsWLAN(FakeWLAN):
    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))


class NetworkManagerTests(unittest.TestCase):
    def test_selects_strongest_visible_configured_network(self):
        scans = [
            (b"Phone Hotspot", b"", 1, -45, 0, 0),
            (b"Home WiFi", b"", 6, -80, 0, 0),
            (b"Other", b"", 11, -30, 0, 0),
        ]
        configured = [
            {"ssid": "Home WiFi", "password": ""},
            {"ssid": "Phone Hotspot", "password": ""},
        ]
        selected = select_configured_network(scans, configured)
        self.assertEqual(selected["ssid"], "Phone Hotspot")

    def test_tie_breaks_by_configured_order(self):
        scans = [
            (b"Phone Hotspot", b"", 1, -50, 0, 0),
            (b"Home WiFi", b"", 6, -50, 0, 0),
        ]
        configured = [
            {"ssid": "Home WiFi", "password": ""},
            {"ssid": "Phone Hotspot", "password": ""},
        ]
        selected = select_configured_network(scans, configured)
        self.assertEqual(selected["ssid"], "Home WiFi")

    def test_does_not_try_unavailable_networks(self):
        wlan = FakeWLAN([(b"Other", b"", 1, -30, 0, 0)])
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
        )
        self.assertFalse(manager.ensure_connected())
        self.assertEqual(wlan.connect_calls, [])

    def test_uses_visible_standard_secrets_fallback(self):
        wlan = FakeWLAN([(b"Fallback", b"", 1, -40, 0, 0)])
        manager = NetworkManager(
            wifi_networks=[],
            wlan=wlan,
            secrets_loader=lambda: {"ssid": "Fallback", "password": ""},
        )
        self.assertTrue(manager.ensure_connected())
        self.assertEqual(wlan.connect_calls, [("Fallback", "")])

    def test_keeps_existing_connection(self):
        wlan = FakeWLAN([], connected=True)
        manager = NetworkManager(wifi_networks=[], wlan=wlan)
        self.assertTrue(manager.ensure_connected())
        self.assertEqual(wlan.connect_calls, [])

    def test_no_matching_ssid_returns_false_without_exception(self):
        wlan = FakeWLAN([(b"Other", b"", 1, -30, 0, 0)])
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Missing", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
        )
        self.assertFalse(manager.ensure_connected())

    def test_connect_oserror_returns_false_without_exception(self):
        wlan = FakeWLAN(
            [(b"Home WiFi", b"", 1, -40, 0, 0)],
            connect_error=OSError("join failed"),
        )
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
        )
        self.assertFalse(manager.ensure_connected())

    def test_connection_timeout_returns_false_without_exception(self):
        wlan = NeverConnectsWLAN([(b"Home WiFi", b"", 1, -40, 0, 0)])
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
            connect_timeout_ms=0,
        )
        self.assertFalse(manager.ensure_connected())
        self.assertEqual(wlan.connect_calls, [("Home WiFi", "")])

    def test_scan_exceptions_return_false_without_exception(self):
        wlan = FakeWLAN([], scan_error=OSError("scan failed"))
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
        )
        self.assertFalse(manager.ensure_connected())

    def test_wlan_activation_exceptions_return_false_without_exception(self):
        wlan = FakeWLAN([], active_error=OSError("active failed"))
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
        )
        self.assertFalse(manager.ensure_connected())

    def test_isconnected_exceptions_return_false_without_exception(self):
        wlan = FakeWLAN(
            [(b"Home WiFi", b"", 1, -40, 0, 0)],
            isconnected_error=OSError("status failed"),
        )
        manager = NetworkManager(
            wifi_networks=[{"ssid": "Home WiFi", "password": ""}],
            wlan=wlan,
            fallback_to_secrets=False,
            connect_timeout_ms=0,
        )
        self.assertFalse(manager.ensure_connected())

    def test_runtime_networking_avoids_fatal_paths(self):
        for path in (ROOT / "profile_hub").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("fatal_error(", text)
            self.assertNotIn("wifi.connect(", text)
            self.assertNotIn("machine.reset(", text)


if __name__ == "__main__":
    unittest.main()
