import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

from network_manager import NetworkManager, select_configured_network


class FakeWLAN:
    def __init__(self, scans, connected=False):
        self.scans = scans
        self.connected = connected
        self.connect_calls = []

    def active(self, value):
        self.active_value = value

    def isconnected(self):
        return self.connected

    def scan(self):
        return self.scans

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        self.connected = True


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


if __name__ == "__main__":
    unittest.main()
