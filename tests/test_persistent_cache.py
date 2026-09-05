import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

import persistent_cache


class PersistentCacheTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(persistent_cache)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "profile_cache.json"
        self.temp_path = Path(self.temp_dir.name) / "profile_cache.tmp"

    def write_raw(self, payload):
        self.path.write_text(payload, encoding="utf-8")

    def write_json(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def load_json(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, name, data, now=1000, last_write=None):
        return persistent_cache.save_integration(
            name,
            data,
            now,
            last_write,
            path=str(self.path),
            temp_path=str(self.temp_path),
        )

    def test_missing_cache_file_no_crash(self):
        self.assertEqual(persistent_cache.load_cache(str(self.path)), {"version": 1})
        self.assertIsNone(persistent_cache.load_integration("wdgwars", str(self.path)))

    def test_malformed_json_no_crash(self):
        self.write_raw("{not json")

        self.assertEqual(persistent_cache.load_cache(str(self.path)), {"version": 1})

    def test_unsupported_version_is_ignored(self):
        self.write_json({"version": 99, "wdgwars": {"data": {"username": "old"}}})

        self.assertIsNone(persistent_cache.load_integration("wdgwars", str(self.path)))

    def test_valid_wdgwars_cache_restores_data(self):
        data = {"username": "demo", "rank_all": 1, "wifi": 10}
        self.write_json({"version": 1, "wdgwars": {"data": data}})

        self.assertEqual(persistent_cache.load_integration("wdgwars", str(self.path)), data)

    def test_valid_wigle_cache_restores_data(self):
        data = {"username": "demo", "global_rank": 100, "cell": 3}
        self.write_json({"version": 1, "wigle": {"data": data}})

        self.assertEqual(persistent_cache.load_integration("wigle", str(self.path)), data)

    def test_absolute_default_cache_path_is_used(self):
        self.assertEqual(
            persistent_cache.CACHE_PATH,
            "/profile_hub_cache.json",
        )

    def test_absolute_default_temp_path_is_used(self):
        self.assertEqual(
            persistent_cache.TEMP_PATH,
            "/profile_hub_cache.tmp",
        )

    def test_runtime_writes_do_not_target_system_filesystem(self):
        self.assertNotIn("/system", persistent_cache.CACHE_PATH)
        self.assertNotIn("/system", persistent_cache.TEMP_PATH)

    def test_corrupted_individual_integration_does_not_break_other_integration(self):
        wigle = {"username": "demo", "global_rank": 100}
        self.write_json(
            {
                "version": 1,
                "wdgwars": {"data": ["bad"]},
                "wigle": {"data": wigle},
            }
        )

        self.assertIsNone(persistent_cache.load_integration("wdgwars", str(self.path)))
        self.assertEqual(persistent_cache.load_integration("wigle", str(self.path)), wigle)

    def test_cache_contains_no_api_credentials(self):
        self.save(
            "wdgwars",
            {
                "username": "demo",
                "rank_all": 1,
                "WDGWARS_API_KEY": "secret",
                "wigle_api_name": "secret",
                "wigle_api_token": "secret",
            },
        )

        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("secret", text)
        self.assertNotIn("WDGWARS_API_KEY", text)
        self.assertNotIn("wigle_api_name", text)
        self.assertNotIn("wigle_api_token", text)

    def test_cache_contains_no_wifi_credentials(self):
        self.save(
            "wigle",
            {
                "username": "demo",
                "global_rank": 100,
                "WIFI_SSID": "secret-network",
                "WIFI_PASSWORD": "secret-password",
            },
        )

        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("secret-network", text)
        self.assertNotIn("secret-password", text)
        self.assertNotIn("WIFI_SSID", text)
        self.assertNotIn("WIFI_PASSWORD", text)

    def test_first_successful_fetch_may_write_immediately(self):
        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1000)

        self.assertTrue(wrote)
        self.assertEqual(last_write, 1000)
        self.assertEqual(
            self.load_json()["wdgwars"]["data"],
            {"username": "demo"},
        )

    def test_no_cache_first_successful_wdgwars_live_creates_file(self):
        self.assertFalse(self.path.exists())

        last_write, wrote = self.save(
            "wdgwars",
            {"username": "demo", "rank_all": 1},
            now=0,
            last_write=None,
        )

        self.assertTrue(wrote)
        self.assertEqual(last_write, 0)
        self.assertTrue(self.path.exists())
        self.assertEqual(self.load_json()["wdgwars"]["data"]["rank_all"], 1)

    def test_no_cache_first_successful_wigle_live_creates_file(self):
        self.assertFalse(self.path.exists())

        last_write, wrote = self.save(
            "wigle",
            {"username": "demo", "global_rank": 100},
            now=0,
            last_write=None,
        )

        self.assertTrue(wrote)
        self.assertEqual(last_write, 0)
        self.assertTrue(self.path.exists())
        self.assertEqual(self.load_json()["wigle"]["data"]["global_rank"], 100)

    def test_first_write_is_not_blocked_by_cooldown(self):
        last_write, wrote = persistent_cache.save_integration(
            "wdgwars",
            {"username": "demo"},
            1,
            None,
            min_interval_ms=999999,
            path=str(self.path),
            temp_path=str(self.temp_path),
        )

        self.assertTrue(wrote)
        self.assertEqual(last_write, 1)

    def test_first_write_is_not_blocked_by_identical_data_comparison(self):
        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1)

        self.assertTrue(wrote)
        self.assertEqual(last_write, 1)

    def test_identical_data_is_not_rewritten(self):
        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1000)
        mtime = self.path.stat().st_mtime_ns

        last_write, wrote = self.save(
            "wdgwars",
            {"username": "demo"},
            now=2000,
            last_write=last_write,
        )

        self.assertFalse(wrote)
        self.assertEqual(last_write, 1000)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)

    def test_changed_data_is_persisted_after_cooldown(self):
        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1000)

        last_write, wrote = self.save(
            "wdgwars",
            {"username": "demo", "rank_all": 1},
            now=1000 + persistent_cache.WRITE_COOLDOWN_MS,
            last_write=last_write,
        )

        self.assertTrue(wrote)
        self.assertEqual(last_write, 1000 + persistent_cache.WRITE_COOLDOWN_MS)
        self.assertEqual(self.load_json()["wdgwars"]["data"]["rank_all"], 1)

    def test_later_writes_respect_persistent_write_cooldown(self):
        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1000)

        last_write, wrote = self.save(
            "wdgwars",
            {"username": "demo", "rank_all": 2},
            now=1000 + persistent_cache.WRITE_COOLDOWN_MS - 1,
            last_write=last_write,
        )

        self.assertFalse(wrote)
        self.assertEqual(last_write, 1000)
        self.assertNotIn("rank_all", self.load_json()["wdgwars"]["data"])

    def test_write_failure_returns_false_without_exception(self):
        original_open = open

        def failing_open(path, mode="r"):
            if "w" in mode:
                raise OSError(30)
            return original_open(path, mode)

        persistent_cache.open = failing_open
        self.addCleanup(lambda: setattr(persistent_cache, "open", original_open))

        last_write, wrote = self.save("wdgwars", {"username": "demo"}, now=1000)

        self.assertFalse(wrote)
        self.assertIsNone(last_write)

    def test_integrations_load_independently_from_same_cache(self):
        self.write_json(
            {
                "version": 1,
                "wdgwars": {"data": {"username": "wdg"}},
                "wigle": {"data": {"username": "wigle"}},
            }
        )

        self.assertEqual(
            persistent_cache.load_integration("wdgwars", str(self.path)),
            {"username": "wdg"},
        )
        self.assertEqual(
            persistent_cache.load_integration("wigle", str(self.path)),
            {"username": "wigle"},
        )


if __name__ == "__main__":
    unittest.main()
