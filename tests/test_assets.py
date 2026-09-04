import unittest
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class AssetTests(unittest.TestCase):
    def test_icon_is_24_by_24_png(self):
        path = ROOT / "profile_hub" / "icon.png"
        with Image.open(path) as image:
            self.assertEqual(image.size, (24, 24))
            self.assertEqual(image.format, "PNG")

    def test_private_credential_files_are_not_tracked(self):
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked = set(result.stdout.splitlines())
        self.assertNotIn("profile.json", tracked)
        self.assertNotIn("credentials.json", tracked)
        self.assertFalse(any(path.startswith("dist/") for path in tracked))

        placeholder = (ROOT / "profile_hub" / "profile_config.py").read_text(encoding="utf-8")
        self.assertIn('WDGWARS_API_KEY = ""', placeholder)
        self.assertIn('WIGLE_API_NAME = ""', placeholder)
        self.assertIn('WIGLE_API_TOKEN = ""', placeholder)


if __name__ == "__main__":
    unittest.main()
