import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

runtime = importlib.import_module("profile_hub")


SIX_HOURS_MS = 6 * 60 * 60 * 1000
COOLDOWN_MS = 60 * 1000


class Fetcher:
    def __init__(self, key):
        self.key = key
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return "LIVE", {self.key: len(self.calls)}


class OfflineFetcher:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        previous = args[-1]
        return "OFFLINE", previous


class ConnectingFetcher:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        previous = args[-1]
        return "CONNECTING", previous


class FakePersistentCache:
    def __init__(self, cached=None):
        self.cached = cached or {}
        self.loads = []
        self.saves = []

    def load_integration(self, name):
        self.loads.append(name)
        return self.cached.get(name)

    def save_integration(self, name, data, now_ms, last_write_ms):
        self.saves.append((name, data, now_ms, last_write_ms))
        return now_ms, True


class FailingPersistentCache(FakePersistentCache):
    def save_integration(self, name, data, now_ms, last_write_ms):
        self.saves.append((name, data, now_ms, last_write_ms))
        raise OSError("rename failed")


class FakeBadge:
    def __init__(self, ticks, pressed=()):
        self.ticks = ticks
        self._pressed = set(pressed)

    def pressed(self, button):
        return button in self._pressed


class RuntimeRefreshTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(runtime)
        self.wdg_fetch = Fetcher("wdg")
        self.wigle_fetch = Fetcher("wigle")
        runtime.wdgwars.fetch = self.wdg_fetch
        runtime.wigle.fetch = self.wigle_fetch
        self.cache = FakePersistentCache()
        runtime.persistent_cache = self.cache
        self.configure_runtime()

    def configure_runtime(
        self,
        wdg_key="wdg-key",
        wigle_name="wigle-name",
        wigle_token="wigle-token",
    ):
        runtime.cfg = SimpleNamespace(
            LINKS=[],
            PAGE_ORDER=["main", "wdgwars", "wigle"],
            NAME_LINE1="Your",
            NAME_LINE2="Name",
            JOB_TITLE="Wireless Intelligence Engineer",
            PRIMARY_LABEL="example.com",
            TAGLINE="XIAO C5 // RF // CYBER",
            WDGWARS_ENABLED=True,
            WDGWARS_API_KEY=wdg_key,
            WDGWARS_REFRESH_MS=SIX_HOURS_MS,
            WDGWARS_PAGE_ENTRY_COOLDOWN_MS=COOLDOWN_MS,
            WIGLE_ENABLED=True,
            WIGLE_API_NAME=wigle_name,
            WIGLE_API_TOKEN=wigle_token,
            WIGLE_REFRESH_MS=SIX_HOURS_MS,
            WIGLE_PAGE_ENTRY_COOLDOWN_MS=COOLDOWN_MS,
            RETRY_MS=COOLDOWN_MS,
            INPUT_DELAY_MS=180,
        )
        runtime.PAGES = ["main", "wdgwars", "wigle"]
        runtime.page_index = 0
        runtime.last_page_id = None
        runtime.last_input = -999999
        runtime.wdg_data = None
        runtime.wdg_status = "IDLE"
        runtime.wdg_last_sync = -SIX_HOURS_MS
        runtime.wdg_last_attempt = -COOLDOWN_MS
        runtime.wigle_data = None
        runtime.wigle_status = "IDLE"
        runtime.wigle_last_sync = -SIX_HOURS_MS
        runtime.wigle_last_attempt = -COOLDOWN_MS
        runtime.wdg_cache_last_write = None
        runtime.wigle_cache_last_write = None
        runtime.BUTTON_A = "A"
        runtime.BUTTON_B = "B"
        runtime.BUTTON_C = "C"

    def set_badge(self, ticks, pressed=()):
        runtime.badge = FakeBadge(ticks, pressed)

    def test_no_api_calls_automatically_at_app_start(self):
        runtime.refresh_current(0, entered=False)

        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_no_background_api_call_when_main_page_remains_visible_after_six_hours(self):
        runtime.refresh_current(SIX_HOURS_MS + 1, entered=False)

        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_page_entry_refreshes_wdgwars(self):
        runtime.page_index = 1

        runtime.refresh_current(1000, entered=True)

        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(runtime.wdg_status, "LIVE")
        self.assertEqual(runtime.wdg_data, {"wdg": 1})

    def test_page_entry_refreshes_wigle(self):
        runtime.page_index = 2

        runtime.refresh_current(1000, entered=True)

        self.assertEqual(len(self.wigle_fetch.calls), 1)
        self.assertEqual(runtime.wigle_status, "LIVE")
        self.assertEqual(runtime.wigle_data, {"wigle": 1})

    def test_page_entry_cooldown_remains_per_integration(self):
        runtime.page_index = 1
        runtime.refresh_current(1000, entered=True)
        runtime.refresh_current(1000 + COOLDOWN_MS - 1, entered=True)
        runtime.refresh_current(1000 + COOLDOWN_MS + 1, entered=True)

        self.assertEqual(len(self.wdg_fetch.calls), 2)
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_current_integration_page_refreshes_after_configured_six_hours(self):
        runtime.page_index = 1
        runtime.wdg_last_sync = 1000

        runtime.refresh_current(1000 + SIX_HOURS_MS, entered=False)
        self.assertEqual(self.wdg_fetch.calls, [])

        runtime.refresh_current(1000 + SIX_HOURS_MS + 1, entered=False)
        self.assertEqual(len(self.wdg_fetch.calls), 1)

    def test_offline_failure_preserves_wdgwars_cached_data(self):
        previous = {"username": "cached", "rank_all": 1}
        runtime.page_index = 1
        runtime.wdg_data = previous
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIs(runtime.wdg_data, previous)
        self.assertEqual(runtime.wdg_status, "CACHED")
        self.assertEqual(runtime.wdg_last_sync, 1000)

    def test_offline_failure_preserves_wigle_cached_data(self):
        previous = {"username": "cached", "global_rank": 100}
        runtime.page_index = 2
        runtime.wigle_data = previous
        runtime.wigle.fetch = OfflineFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIs(runtime.wigle_data, previous)
        self.assertEqual(runtime.wigle_status, "CACHED")
        self.assertEqual(runtime.wigle_last_sync, 1000)

    def test_connecting_status_does_not_replace_cached_data_or_sync_time(self):
        previous = {"username": "cached", "rank_all": 1}
        runtime.page_index = 1
        runtime.wdg_data = previous
        runtime.wdgwars.fetch = ConnectingFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIs(runtime.wdg_data, previous)
        self.assertEqual(runtime.wdg_status, "CONNECTING")
        self.assertEqual(runtime.wdg_last_sync, -SIX_HOURS_MS)

    def test_navigation_forward_back_home_works_before_refresh(self):
        drawn = []
        runtime.draw = lambda: drawn.append(runtime.PAGES[runtime.page_index])
        runtime.PAGES = ["main", "website", "wdgwars", "wigle"]
        runtime.page_index = 1
        runtime.last_page_id = "website"
        self.set_badge(1000, ("B",))

        runtime.update()

        self.assertEqual(runtime.page_index, 2)
        self.assertEqual(drawn, ["wdgwars"])
        self.assertEqual(len(self.wdg_fetch.calls), 1)

        self.set_badge(2000, ("A",))
        runtime.update()
        self.assertEqual(runtime.page_index, 1)

        self.set_badge(3000, ("C",))
        runtime.update()
        self.assertEqual(runtime.page_index, 0)

    def test_blank_credentials_show_setup_without_fetch_call(self):
        self.configure_runtime(wdg_key="", wigle_name="", wigle_token="")
        runtime.wdgwars = importlib.reload(runtime.wdgwars)
        runtime.wigle = importlib.reload(runtime.wigle)

        runtime.page_index = 1
        runtime.refresh_current(1000, entered=True)
        runtime.page_index = 2
        runtime.refresh_current(2000, entered=True)

        self.assertEqual(runtime.wdg_status, "NO KEY")
        self.assertEqual(runtime.wigle_status, "NO KEY")

    def test_valid_wdgwars_cache_restores_data_as_cached_without_api_request(self):
        cached = {"username": "cached", "rank_all": 2}
        self.cache = FakePersistentCache({"wdgwars": cached})
        runtime.persistent_cache = self.cache

        runtime.load_persistent_stats()

        self.assertIs(runtime.wdg_data, cached)
        self.assertEqual(runtime.wdg_status, "CACHED")
        self.assertEqual(self.wdg_fetch.calls, [])

    def test_valid_wigle_cache_restores_data_as_cached_without_api_request(self):
        cached = {"username": "cached", "global_rank": 100}
        self.cache = FakePersistentCache({"wigle": cached})
        runtime.persistent_cache = self.cache

        runtime.load_persistent_stats()

        self.assertIs(runtime.wigle_data, cached)
        self.assertEqual(runtime.wigle_status, "CACHED")
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_cache_restore_requires_configured_credentials(self):
        cached = {
            "wdgwars": {"username": "cached"},
            "wigle": {"username": "cached"},
        }
        self.configure_runtime(wdg_key="", wigle_name="", wigle_token="")
        self.cache = FakePersistentCache(cached)
        runtime.persistent_cache = self.cache

        runtime.load_persistent_stats()

        self.assertIsNone(runtime.wdg_data)
        self.assertIsNone(runtime.wigle_data)
        self.assertEqual(runtime.wdg_status, "IDLE")
        self.assertEqual(runtime.wigle_status, "IDLE")

    def test_successful_live_wdgwars_fetch_persists_data(self):
        runtime.page_index = 1

        runtime.refresh_current(1000, entered=True)

        self.assertEqual(
            self.cache.saves,
            [("wdgwars", {"wdg": 1}, 1000, None)],
        )

    def test_successful_live_wigle_fetch_persists_data(self):
        runtime.page_index = 2

        runtime.refresh_current(1000, entered=True)

        self.assertEqual(
            self.cache.saves,
            [("wigle", {"wigle": 1}, 1000, None)],
        )

    def test_failed_fetch_never_persists_over_previous_good_data(self):
        previous = {"username": "cached", "rank_all": 1}
        runtime.page_index = 1
        runtime.wdg_data = previous
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIs(runtime.wdg_data, previous)
        self.assertEqual(runtime.wdg_status, "CACHED")
        self.assertEqual(self.cache.saves, [])

    def test_offline_with_persistent_data_remains_cached(self):
        cached = {"username": "cached", "rank_all": 2}
        self.cache = FakePersistentCache({"wdgwars": cached})
        runtime.persistent_cache = self.cache
        runtime.load_persistent_stats()
        runtime.page_index = 1
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIs(runtime.wdg_data, cached)
        self.assertEqual(runtime.wdg_status, "CACHED")

    def test_offline_without_cache_remains_offline(self):
        runtime.page_index = 1
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_current(1000, entered=True)

        self.assertIsNone(runtime.wdg_data)
        self.assertEqual(runtime.wdg_status, "OFFLINE")

    def test_simulated_rename_failure_does_not_destroy_ram_data(self):
        self.cache = FailingPersistentCache()
        runtime.persistent_cache = self.cache
        runtime.page_index = 1

        runtime.refresh_current(1000, entered=True)

        self.assertEqual(runtime.wdg_status, "LIVE")
        self.assertEqual(runtime.wdg_data, {"wdg": 1})
        self.assertEqual(
            self.cache.saves,
            [("wdgwars", {"wdg": 1}, 1000, None)],
        )


if __name__ == "__main__":
    unittest.main()
