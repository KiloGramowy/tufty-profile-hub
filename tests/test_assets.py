import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class AssetTests(unittest.TestCase):
    def test_icon_is_24_by_24_png(self):
        path = ROOT / "profile_hub" / "icon.png"
        with Image.open(path) as image:
            self.assertEqual(image.size, (24, 24))
            self.assertEqual(image.format, "PNG")


if __name__ == "__main__":
    unittest.main()
