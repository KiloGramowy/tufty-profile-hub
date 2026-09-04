import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build_profile


class BuilderTests(unittest.TestCase):
    def load_examples(self):
        profile = build_profile.load_json(ROOT / "profile.example.json")
        credentials = build_profile.load_json(ROOT / "credentials.example.json")
        return profile, credentials

    def test_json_examples_validate(self):
        for path in [
            ROOT / "profile.example.json",
            ROOT / "credentials.example.json",
            ROOT / "presets" / "kilo_demo.json",
        ]:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.assertIsInstance(data, dict)

    def test_default_build_generates_dist_and_qr_matrices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "profile_hub"
            config = build_profile.build(
                ROOT / "profile.example.json",
                ROOT / "credentials.example.json",
                out_dir,
            )

            self.assertEqual(
                [page["id"] for page in config["pages"]],
                ["main", "website", "youtube", "github", "wdgwars", "wigle"],
            )
            self.assertTrue((out_dir / "__init__.py").exists())
            self.assertTrue((out_dir / "profile_config.py").exists())
            self.assertTrue((out_dir / "generated_qr.py").exists())

            spec = importlib.util.spec_from_file_location(
                "generated_qr_test", out_dir / "generated_qr.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            website = module.QR_PAGES["website"]
            self.assertEqual(website["url"], "https://example.com")
            self.assertGreater(len(website["matrix"]), 20)
            self.assertEqual(website["matrix"], build_profile.make_qr_matrix("https://example.com"))
            self.assertIn("website", module.QR_CODES)
            n, rows = module.QR_CODES["website"]
            self.assertEqual(n, len(rows))
            self.assertEqual((n, rows), build_profile.make_qr_rows("https://example.com"))

            config_spec = importlib.util.spec_from_file_location(
                "profile_config_test", out_dir / "profile_config.py"
            )
            config_module = importlib.util.module_from_spec(config_spec)
            config_spec.loader.exec_module(config_module)
            self.assertEqual(config_module.NAME_LINE1, "Your")
            self.assertEqual(config_module.PAGE_ORDER, ["main", "website", "youtube", "github", "wdgwars", "wigle"])
            self.assertEqual(config_module.WDGWARS_REFRESH_MS, 6 * 60 * 60 * 1000)
            self.assertEqual(config_module.WDGWARS_PAGE_ENTRY_COOLDOWN_MS, 60 * 1000)
            self.assertEqual(config_module.WIGLE_REFRESH_MS, 6 * 60 * 60 * 1000)
            self.assertEqual(config_module.WIGLE_PAGE_ENTRY_COOLDOWN_MS, 60 * 1000)

    def test_custom_link_is_appended_and_qr_generated(self):
        profile, credentials = self.load_examples()
        profile["links"].append(
            {
                "id": "mastodon",
                "title": "MASTODON",
                "label": "@user@example.social",
                "url": "https://example.social/@user",
                "accent": "blue",
            }
        )
        config = build_profile.normalize(profile, credentials)
        self.assertIn("mastodon", [page["id"] for page in config["pages"]])

    def test_duplicate_link_id_validation(self):
        profile, credentials = self.load_examples()
        profile["links"].append(dict(profile["links"][0]))
        with self.assertRaisesRegex(build_profile.ConfigError, "duplicate link id"):
            build_profile.normalize(profile, credentials)

    def test_page_order_validation(self):
        profile, credentials = self.load_examples()
        profile["page_order"] = ["main", "website", "not-a-real-page"]
        with self.assertRaisesRegex(build_profile.ConfigError, "unknown page id"):
            build_profile.normalize(profile, credentials)

    def test_invalid_configuration_handling(self):
        profile, credentials = self.load_examples()
        profile.pop("name_line1")
        with self.assertRaisesRegex(build_profile.ConfigError, "name_line1"):
            build_profile.normalize(profile, credentials)

    def test_disabled_integrations_are_removed_from_pages(self):
        profile, credentials = self.load_examples()
        profile["wdgwars"]["enabled"] = False
        profile["wigle"]["enabled"] = False
        config = build_profile.normalize(profile, credentials)
        page_ids = [page["id"] for page in config["pages"]]
        self.assertNotIn("wdgwars", page_ids)
        self.assertNotIn("wigle", page_ids)

    def test_blank_integrations_remain_visible_by_default(self):
        profile, credentials = self.load_examples()
        config = build_profile.normalize(profile, credentials)
        page_ids = [page["id"] for page in config["pages"]]
        self.assertIn("wdgwars", page_ids)
        self.assertIn("wigle", page_ids)
        self.assertEqual(config["integrations"]["wdgwars"]["wdgwars_api_key"], "")
        self.assertEqual(config["integrations"]["wigle"]["wigle_api_name"], "")
        self.assertEqual(config["integrations"]["wigle"]["wigle_api_token"], "")

    def test_multi_wifi_parsing_and_empty_fallback(self):
        profile, credentials = self.load_examples()
        self.assertEqual(build_profile.normalize(profile, credentials)["wifi_networks"], [])
        credentials["wifi_networks"] = [
            {"ssid": "Home WiFi", "password": ""},
            {"ssid": "", "password": ""},
        ]
        config = build_profile.normalize(profile, credentials)
        self.assertEqual(config["wifi_networks"], [{"ssid": "Home WiFi", "password": ""}])

    def test_runtime_sources_do_not_import_host_qr_dependencies(self):
        for path in (ROOT / "profile_hub").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("import qrcode", text)
            self.assertNotIn("from qrcode", text)
            self.assertNotIn("import PIL", text)
            self.assertNotIn("from PIL", text)


if __name__ == "__main__":
    unittest.main()
