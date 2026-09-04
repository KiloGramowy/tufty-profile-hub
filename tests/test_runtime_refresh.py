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
        return "OFFLINE", args[1]


class RaisingFetcher:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        raise OSError("network down")


class ConnectingThenLiveFetcher:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if len(self.calls) == 1:
            return "CONNECTING", args[1]
        return "LIVE", {"username": "fresh"}


class FakeBadge:
    def __init__(self, ticks, pressed=()):
        self.ticks = ticks
        self._pressed = set(pressed)

    def pressed(self, button):
        return button in self._pressed


class RuntimeRefreshTests(unittest.TestCase):
    def setUp(self):
        self.wdg_fetch = Fetcher("wdg")
        self.wigle_fetch = Fetcher("wigle")
        runtime.wdgwars.fetch = self.wdg_fetch
        runtime.wigle.fetch = self.wigle_fetch
        self.configure_runtime()

    def configure_runtime(self, start=0, wdg_key="wdg-key", wigle_name="wigle-name", wigle_token="wigle-token"):
        runtime.cfg = SimpleNamespace(
            WDGWARS_ENABLED=True,
            WDGWARS_API_KEY=wdg_key,
            WDGWARS_REFRESH_MS=SIX_HOURS_MS,
            WDGWARS_PAGE_ENTRY_COOLDOWN_MS=COOLDOWN_MS,
            WIGLE_ENABLED=True,
            WIGLE_API_NAME=wigle_name,
            WIGLE_API_TOKEN=wigle_token,
            WIGLE_REFRESH_MS=SIX_HOURS_MS,
            WIGLE_PAGE_ENTRY_COOLDOWN_MS=COOLDOWN_MS,
            INPUT_DELAY_MS=180,
        )
        runtime.PAGES = ["main", "wdgwars", "wigle"]
        runtime.page_index = 0
        runtime.last_page_id = None
        runtime.last_input = None
        runtime.wdg_data = None
        runtime.wdg_status = "IDLE"
        runtime.wdg_last_success = None
        runtime.wdg_last_attempt = None
        runtime.wdg_next_auto = runtime.ticks_add(start, SIX_HOURS_MS)
        runtime.wdg_refresh_pending = None
        runtime.wigle_data = None
        runtime.wigle_status = "IDLE"
        runtime.wigle_last_success = None
        runtime.wigle_last_attempt = None
        runtime.wigle_next_auto = runtime.ticks_add(start, SIX_HOURS_MS)
        runtime.wigle_refresh_pending = None
        runtime.BUTTON_A = "A"
        runtime.BUTTON_B = "B"
        runtime.BUTTON_C = "C"

    def set_badge(self, ticks, pressed=()):
        runtime.badge = FakeBadge(ticks, pressed)

    def test_no_background_api_calls_at_app_start(self):
        runtime.refresh_background(0)
        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_high_app_start_ticks_do_not_make_background_refresh_immediately_due(self):
        start = (1 << 30) + 12345
        self.configure_runtime(start=start)

        runtime.refresh_background(start)
        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])
        self.assertEqual(runtime.wdg_next_auto, start + SIX_HOURS_MS)
        self.assertEqual(runtime.wigle_next_auto, start + SIX_HOURS_MS)

        runtime.refresh_background(start + SIX_HOURS_MS)
        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(len(self.wigle_fetch.calls), 1)

    def test_both_integrations_are_due_after_six_hours_on_main_page(self):
        runtime.page_index = 0
        runtime.refresh_current(SIX_HOURS_MS - 1, entered=False)
        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])

        runtime.refresh_current(SIX_HOURS_MS, entered=False)
        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(len(self.wigle_fetch.calls), 1)

    def test_page_entry_refresh_resets_auto_timer(self):
        page_entry_at = 60 * 60 * 1000
        runtime.refresh_page_entry(page_entry_at, "wdgwars")
        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(runtime.wdg_next_auto, page_entry_at + SIX_HOURS_MS)

        runtime.refresh_background(SIX_HOURS_MS)
        self.assertEqual(len(self.wdg_fetch.calls), 1)

        runtime.refresh_background(page_entry_at + SIX_HOURS_MS)
        self.assertEqual(len(self.wdg_fetch.calls), 2)

    def test_entering_wdgwars_queues_refresh_after_destination_draw(self):
        drawn = []
        runtime.draw = lambda: drawn.append(runtime.PAGES[runtime.page_index])
        runtime.PAGES = ["main", "website", "wdgwars", "wigle"]
        runtime.page_index = 1
        runtime.last_page_id = "website"
        self.set_badge(1000, ("B",))

        runtime.update()

        self.assertEqual(runtime.page_index, 2)
        self.assertEqual(drawn, ["wdgwars"])
        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(runtime.wdg_refresh_pending, "queued")

    def test_navigation_wins_while_refresh_is_pending(self):
        drawn = []
        runtime.draw = lambda: drawn.append(runtime.PAGES[runtime.page_index])
        runtime.PAGES = ["main", "website", "wdgwars", "wigle"]
        runtime.page_index = 2
        runtime.last_page_id = "wdgwars"
        runtime.wdg_refresh_pending = "connecting"
        self.set_badge(1000, ("A",))

        runtime.update()

        self.assertEqual(runtime.page_index, 1)
        self.assertEqual(drawn, ["website"])
        self.assertEqual(self.wdg_fetch.calls, [])

    def test_connecting_continuation_bypasses_new_attempt_cooldown(self):
        fetcher = ConnectingThenLiveFetcher()
        runtime.wdgwars.fetch = fetcher
        runtime.wdg_refresh_pending = "queued"

        runtime.refresh_current(1000, entered=False)
        self.assertEqual(runtime.wdg_status, "CONNECTING")
        self.assertEqual(runtime.wdg_refresh_pending, "connecting")
        self.assertEqual(runtime.wdg_last_attempt, 1000)

        runtime.refresh_current(1001, entered=False)
        self.assertEqual(len(fetcher.calls), 2)
        self.assertIsNone(runtime.wdg_refresh_pending)
        self.assertEqual(runtime.wdg_status, "LIVE")
        self.assertEqual(runtime.wdg_data, {"username": "fresh"})

    def test_failed_auto_refresh_does_not_retry_after_sixty_seconds(self):
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_background(SIX_HOURS_MS)
        runtime.refresh_background(SIX_HOURS_MS + COOLDOWN_MS)

        self.assertEqual(len(runtime.wdgwars.fetch.calls), 1)
        self.assertEqual(runtime.wdg_status, "OFFLINE")
        self.assertEqual(runtime.wdg_next_auto, SIX_HOURS_MS * 2)

    def test_failed_auto_refresh_becomes_due_again_after_six_hours(self):
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_background(SIX_HOURS_MS)
        runtime.refresh_background(SIX_HOURS_MS * 2 - 1)
        self.assertEqual(len(runtime.wdgwars.fetch.calls), 1)

        runtime.refresh_background(SIX_HOURS_MS * 2)
        self.assertEqual(len(runtime.wdgwars.fetch.calls), 2)

    def test_successful_auto_refresh_schedules_next_attempt_after_six_hours(self):
        runtime.refresh_background(SIX_HOURS_MS)
        runtime.refresh_background(SIX_HOURS_MS + COOLDOWN_MS)

        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(runtime.wdg_last_success, SIX_HOURS_MS)
        self.assertEqual(runtime.wdg_next_auto, SIX_HOURS_MS * 2)

    def test_failed_page_entry_postpones_background_auto_attempt(self):
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_page_entry(SIX_HOURS_MS + 1000, "wdgwars")
        runtime.refresh_background(SIX_HOURS_MS + COOLDOWN_MS + 1000)

        self.assertEqual(len(runtime.wdgwars.fetch.calls), 1)
        self.assertEqual(runtime.wdg_next_auto, SIX_HOURS_MS * 2 + 1000)

    def test_successful_page_entry_postpones_background_auto_attempt(self):
        runtime.refresh_page_entry(SIX_HOURS_MS + 1000, "wdgwars")
        runtime.refresh_background(SIX_HOURS_MS + COOLDOWN_MS + 1000)

        self.assertEqual(len(self.wdg_fetch.calls), 1)
        self.assertEqual(runtime.wdg_next_auto, SIX_HOURS_MS * 2 + 1000)

    def test_manual_page_entry_may_retry_after_sixty_seconds_when_auto_not_due(self):
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_page_entry(1000, "wdgwars")
        runtime.refresh_page_entry(1000 + COOLDOWN_MS, "wdgwars")

        self.assertEqual(len(runtime.wdgwars.fetch.calls), 2)
        self.assertEqual(runtime.wdg_next_auto, 1000 + COOLDOWN_MS + SIX_HOURS_MS)

    def test_page_entry_cooldown_remains_per_integration(self):
        runtime.refresh_page_entry(1000, "wdgwars")
        runtime.refresh_page_entry(1000 + COOLDOWN_MS - 1, "wdgwars")
        runtime.refresh_page_entry(1000 + COOLDOWN_MS, "wdgwars")

        self.assertEqual(len(self.wdg_fetch.calls), 2)
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_offline_failure_preserves_wdgwars_cached_data(self):
        previous = {"username": "cached", "rank_all": 1}
        runtime.wdg_data = previous
        runtime.wdgwars.fetch = OfflineFetcher()

        runtime.refresh_page_entry(1000, "wdgwars")

        self.assertIs(runtime.wdg_data, previous)
        self.assertEqual(runtime.wdg_status, "CACHED")
        self.assertIsNone(runtime.wdg_last_success)
        self.assertEqual(runtime.wdg_next_auto, 1000 + SIX_HOURS_MS)

    def test_offline_failure_preserves_wigle_cached_data(self):
        previous = {"username": "cached", "global_rank": 100}
        runtime.wigle_data = previous
        runtime.wigle.fetch = OfflineFetcher()

        runtime.refresh_page_entry(1000, "wigle")

        self.assertIs(runtime.wigle_data, previous)
        self.assertEqual(runtime.wigle_status, "CACHED")
        self.assertIsNone(runtime.wigle_last_success)
        self.assertEqual(runtime.wigle_next_auto, 1000 + SIX_HOURS_MS)

    def test_network_oserror_is_absorbed_by_runtime_boundary(self):
        previous = {"username": "cached"}
        runtime.wdg_data = previous
        runtime.wdgwars.fetch = RaisingFetcher()

        runtime.refresh_page_entry(1000, "wdgwars")

        self.assertIs(runtime.wdg_data, previous)
        self.assertEqual(runtime.wdg_status, "CACHED")
        self.assertIsNone(runtime.wdg_last_success)
        self.assertEqual(runtime.wdg_next_auto, 1000 + SIX_HOURS_MS)

    def test_network_oserror_without_cached_data_reports_offline(self):
        runtime.wdgwars.fetch = RaisingFetcher()
        runtime.wigle.fetch = RaisingFetcher()

        runtime.refresh_page_entry(1000, "wdgwars")
        runtime.refresh_page_entry(1000, "wigle")

        self.assertIsNone(runtime.wdg_data)
        self.assertIsNone(runtime.wigle_data)
        self.assertEqual(runtime.wdg_status, "OFFLINE")
        self.assertEqual(runtime.wigle_status, "OFFLINE")

    def test_tick_elapsed_handles_wrap(self):
        wrap = 1 << 30
        self.assertEqual(runtime.ticks_elapsed(500, wrap - 500), 1000)


if __name__ == "__main__":
    unittest.main()
