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
        runtime.wdg_last_sync = start
        runtime.wdg_last_attempt = None
        runtime.wigle_data = None
        runtime.wigle_status = "IDLE"
        runtime.wigle_last_sync = start
        runtime.wigle_last_attempt = None

    def test_no_background_api_calls_at_app_start(self):
        runtime.refresh_background(0)
        self.assertEqual(self.wdg_fetch.calls, [])
        self.assertEqual(self.wigle_fetch.calls, [])

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

        runtime.refresh_background(SIX_HOURS_MS)
        self.assertEqual(len(self.wdg_fetch.calls), 1)

        runtime.refresh_background(page_entry_at + SIX_HOURS_MS)
        self.assertEqual(len(self.wdg_fetch.calls), 2)

    def test_page_entry_cooldown_remains_per_integration(self):
        runtime.refresh_page_entry(1000, "wdgwars")
        runtime.refresh_page_entry(1000 + COOLDOWN_MS - 1, "wdgwars")
        runtime.refresh_page_entry(1000 + COOLDOWN_MS, "wdgwars")

        self.assertEqual(len(self.wdg_fetch.calls), 2)
        self.assertEqual(self.wigle_fetch.calls, [])

    def test_tick_elapsed_handles_wrap(self):
        wrap = 1 << 30
        self.assertEqual(runtime.ticks_elapsed(500, wrap - 500), 1000)


if __name__ == "__main__":
    unittest.main()
