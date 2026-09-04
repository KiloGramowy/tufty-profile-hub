import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

import wdgwars
import wigle


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

    def get(self, url, headers=None):
        self.calls.append({"url": url, "headers": headers or {}})
        return FakeResponse(self.payloads.get(url, {}))


class RaisingRequests:
    def get(self, url, headers=None):
        raise OSError("network down")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(wdgwars)
        importlib.reload(wigle)
        wdgwars.safe_net.connect = lambda: True
        wigle.safe_net.connect = lambda: True

    def test_wdgwars_blank_api_key_makes_no_request(self):
        requests = FakeRequests()
        wdgwars.requests = requests

        self.assertEqual(wdgwars.fetch("", None), ("NO KEY", None))
        self.assertEqual(requests.calls, [])

    def test_wigle_blank_credentials_make_no_request(self):
        requests = FakeRequests()
        wigle.requests = requests

        self.assertEqual(wigle.fetch("", "", None), ("NO KEY", None))
        self.assertEqual(requests.calls, [])

    def test_connecting_network_defers_authenticated_requests(self):
        requests = FakeRequests()
        wdgwars.requests = requests
        wigle.requests = requests
        wdgwars.safe_net.connect = lambda: None
        wigle.safe_net.connect = lambda: None

        self.assertEqual(wdgwars.fetch("demo", None), ("CONNECTING", None))
        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("CONNECTING", None))
        self.assertEqual(requests.calls, [])

    def test_wdgwars_offline_without_previous_data_reports_offline(self):
        wdgwars.requests = FakeRequests()
        wdgwars.safe_net.connect = lambda: False

        self.assertEqual(wdgwars.fetch("demo", None), ("OFFLINE", None))

    def test_wdgwars_offline_refresh_keeps_previous_data(self):
        previous = {"username": "cached"}
        wdgwars.requests = FakeRequests()
        wdgwars.safe_net.connect = lambda: False

        status, data = wdgwars.fetch("demo", previous)

        self.assertEqual(status, "CACHED")
        self.assertIs(data, previous)

    def test_wigle_offline_without_previous_data_reports_offline(self):
        wigle.requests = FakeRequests()
        wigle.safe_net.connect = lambda: False

        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("OFFLINE", None))

    def test_wigle_offline_refresh_keeps_previous_data(self):
        previous = {"username": "cached"}
        wigle.requests = FakeRequests()
        wigle.safe_net.connect = lambda: False

        status, data = wigle.fetch("demo-name", "demo-value", previous)

        self.assertEqual(status, "CACHED")
        self.assertIs(data, previous)

    def test_request_oserror_preserves_previous_data(self):
        previous = {"username": "cached"}
        wdgwars.requests = RaisingRequests()
        wigle.requests = RaisingRequests()

        self.assertEqual(wdgwars.fetch("demo", previous), ("ERROR", previous))
        self.assertEqual(wigle.fetch("demo-name", "demo-value", previous), ("ERROR", previous))

    def test_wdgwars_live_parsing_remains_covered(self):
        wdgwars.requests = FakeRequests(
            {
                "https://wdgwars.pl/api/me": {
                    "ok": True,
                    "username": "demo",
                    "gang": "rf",
                    "gang_role": "operator",
                    "your_rank": {"today": 3, "week": 2, "all_time": 1},
                    "wifi": 10,
                    "ble": 2,
                    "aircraft": 1,
                },
                "https://wdgwars.pl/api/leaderboard": {},
            }
        )

        status, data = wdgwars.fetch("demo", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "demo")
        self.assertEqual(data["rank_all"], 1)
        self.assertEqual(data["ble"], 2)

    def test_wdgwars_leaderboard_aliases_remain_covered(self):
        wdgwars.requests = FakeRequests(
            {
                "https://wdgwars.pl/api/me": {
                    "ok": True,
                    "handle": "demo",
                    "wifi_count": 10,
                    "bluetooth_count": 2,
                    "aircraft_count": 1,
                },
                "https://wdgwars.pl/api/leaderboard": {
                    "today": [{"username": "demo", "position": 3}],
                    "week": [{"username": "demo", "position": 2}],
                    "allTime": [{"username": "demo", "position": 1}],
                },
            }
        )

        status, data = wdgwars.fetch("demo", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["rank_day"], 3)
        self.assertEqual(data["rank_week"], 2)
        self.assertEqual(data["rank_all"], 1)
        self.assertEqual(data["wifi"], 10)

    def test_wigle_live_parsing_remains_covered(self):
        wigle.requests = FakeRequests(
            {
                "https://api.wigle.net/api/v2/profile/user": {"userid": "demo"},
                "https://api.wigle.net/api/v2/stats/user": {
                    "statistics": {
                        "Rank": 100,
                        "MonthRank": 11,
                        "DiscoveredWiFi": 50,
                        "DiscoveredBt": 7,
                        "DiscoveredCell": 3,
                    }
                },
            }
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "demo")
        self.assertEqual(data["global_rank"], 100)
        self.assertEqual(data["month_rank"], 11)
        self.assertEqual(data["cell"], 3)

    def test_wigle_username_falls_back_to_statistics_user_name(self):
        wigle.requests = FakeRequests(
            {
                "https://api.wigle.net/api/v2/profile/user": {"userid": ""},
                "https://api.wigle.net/api/v2/stats/user": {
                    "statistics": {
                        "userName": "stats-user",
                        "rank": 100,
                        "monthRank": 11,
                    }
                },
            }
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "stats-user")

    def test_wigle_basic_auth_header(self):
        self.assertEqual(wigle._basic_header("demo-name", "demo-token")[:6], "Basic ")


if __name__ == "__main__":
    unittest.main()
