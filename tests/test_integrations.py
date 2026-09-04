import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

from wdgwars import WDGWarsClient
from wigle import WiGLEClient, basic_auth_header, normalize_stats


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


class FakeRequests:
    def __init__(self, payloads=None):
        self.payloads = payloads or {}
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        return FakeResponse(self.payloads.get(url, {}))


class OfflineNetwork:
    def ensure_connected(self):
        return False


class Clock:
    def __init__(self, value=1000):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class IntegrationTests(unittest.TestCase):
    def test_wdgwars_blank_api_key_makes_no_request(self):
        requests = FakeRequests()
        client = WDGWarsClient(api_key="", requests_module=requests)
        self.assertEqual(client.page_entry_refresh(), "setup-required")
        self.assertEqual(requests.calls, [])

    def test_wigle_blank_credentials_make_no_request(self):
        requests = FakeRequests()
        client = WiGLEClient(api_name="", api_token="", requests_module=requests)
        self.assertEqual(client.refresh(), "setup-required")
        self.assertEqual(requests.calls, [])

    def test_wdgwars_refresh_policy_and_cooldown(self):
        clock = Clock()
        requests = FakeRequests(
            {
                "https://wdgwars.pl/api/me": {
                    "username": "demo",
                    "wifi": 10,
                    "bluetooth": 2,
                    "aircraft": 1,
                },
                "https://wdgwars.pl/api/leaderboard": {
                    "ranks": {"today": 3, "week": 2, "all_time": 1}
                },
            }
        )
        client = WDGWarsClient(api_key="demo", requests_module=requests, clock=clock)

        self.assertTrue(client.should_auto_refresh())
        self.assertEqual(client.page_entry_refresh(), "ok")
        self.assertEqual(client.page_entry_refresh(), "cooldown")
        clock.advance(60)
        self.assertEqual(client.page_entry_refresh(), "ok")

        self.assertEqual(client.refresh(), "ok")
        self.assertEqual(client.page_entry_refresh(), "cooldown")
        self.assertFalse(client.should_auto_refresh())
        clock.advance((6 * 60 * 60) - 1)
        self.assertFalse(client.should_auto_refresh())
        clock.advance(1)
        self.assertTrue(client.should_auto_refresh())

    def test_wigle_refresh_policy_and_basic_auth(self):
        clock = Clock()
        requests = FakeRequests(
            {
                "https://api.wigle.net/api/v2/profile/user": {"userid": "demo"},
                "https://api.wigle.net/api/v2/stats/user": {
                    "statistics": {
                        "Rank": 100,
                        "MonthRank": 11,
                        "UserName": "demo",
                        "DiscoveredWiFi": 50,
                        "DiscoveredBt": 7,
                        "DiscoveredCell": 3,
                    }
                },
            }
        )
        client = WiGLEClient(
            api_name="demo-name",
            api_token="demo-value",
            requests_module=requests,
            clock=clock,
        )

        self.assertEqual(client.refresh(), "ok")
        self.assertEqual(
            requests.calls[0]["headers"]["Authorization"],
            basic_auth_header("demo-name", "demo-value"),
        )
        self.assertFalse(client.should_auto_refresh())
        clock.advance(6 * 60 * 60)
        self.assertTrue(client.should_auto_refresh())

    def test_wigle_stats_field_variants(self):
        normalized = normalize_stats(
            {
                "statistics": {
                    "rank": 1,
                    "monthlyRank": 2,
                    "username": "demo",
                    "discoveredWiFi": 3,
                    "discoveredBt": 4,
                    "discoveredCell": 5,
                }
            }
        )
        self.assertEqual(normalized["global_rank"], 1)
        self.assertEqual(normalized["monthly_rank"], 2)
        self.assertEqual(normalized["wifi"], 3)
        self.assertEqual(normalized["bluetooth"], 4)
        self.assertEqual(normalized["cellular"], 5)

    def test_offline_refresh_keeps_previous_data(self):
        client = WDGWarsClient(
            api_key="demo",
            requests_module=FakeRequests(),
            network_manager=OfflineNetwork(),
        )
        previous = {"me": {"username": "cached"}}
        client.last_data = previous
        self.assertEqual(client.refresh(), "offline")
        self.assertIs(client.last_data, previous)


if __name__ == "__main__":
    unittest.main()
