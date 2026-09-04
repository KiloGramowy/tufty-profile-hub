import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

runtime = importlib.import_module("profile_hub")


class FakeBadge:
    def __init__(self, light_values=None, exc=None):
        self.light_values = list(light_values or [])
        self.exc = exc
        self.reads = 0

    def light_level(self):
        self.reads += 1
        if self.exc:
            raise self.exc
        if self.light_values:
            return self.light_values.pop(0)
        return 4500


class FakeDisplay:
    def __init__(self):
        self.values = []

    def backlight(self, value):
        self.values.append(value)


class AutoBrightnessTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(runtime)
        runtime.cfg = SimpleNamespace(
            AUTO_BRIGHTNESS_ENABLED=True,
            AUTO_BRIGHTNESS_MIN=0.22,
            AUTO_BRIGHTNESS_MAX=1.0,
        )
        runtime.auto_brightness_last_sample = -runtime.AUTO_BRIGHTNESS_SAMPLE_MS
        runtime.auto_brightness_smoothed = runtime.AUTO_BRIGHTNESS_DEFAULT
        runtime.auto_brightness_applied = runtime.AUTO_BRIGHTNESS_DEFAULT
        runtime.display = FakeDisplay()

    def test_raw_darkness_maps_to_minimum_brightness(self):
        self.assertEqual(runtime.brightness_for_light_level(46), 0.22)
        self.assertEqual(runtime.brightness_for_light_level(80), 0.22)

    def test_indoor_values_map_to_mid_brightness(self):
        value = runtime.brightness_for_light_level(4500)
        self.assertGreaterEqual(value, 0.55)
        self.assertLessEqual(value, 0.70)

    def test_high_ambient_values_map_to_full_brightness(self):
        self.assertEqual(runtime.brightness_for_light_level(60000), 1.0)

    def test_output_never_below_minimum_or_above_maximum(self):
        runtime.cfg.AUTO_BRIGHTNESS_MIN = 0.30
        runtime.cfg.AUTO_BRIGHTNESS_MAX = 0.90

        self.assertEqual(runtime.brightness_for_light_level(0), 0.30)
        self.assertEqual(runtime.brightness_for_light_level(65535), 0.90)

    def test_mapping_is_monotonic(self):
        values = [
            runtime.brightness_for_light_level(raw)
            for raw in (0, 80, 300, 1000, 2500, 5000, 12000, 25000, 65535)
        ]
        self.assertEqual(values, sorted(values))

    def test_small_sensor_fluctuations_do_not_trigger_repeated_backlight_updates(self):
        runtime.auto_brightness_smoothed = runtime.brightness_for_light_level(4500)
        runtime.auto_brightness_applied = runtime.auto_brightness_smoothed
        runtime.badge = FakeBadge([4510, 4520, 4530])

        runtime.update_auto_brightness(1000)
        runtime.update_auto_brightness(1250)
        runtime.update_auto_brightness(1500)

        self.assertEqual(runtime.display.values, [])

    def test_sensor_exception_does_not_crash_runtime_or_change_backlight(self):
        runtime.badge = FakeBadge(exc=OSError("sensor offline"))

        self.assertFalse(runtime.update_auto_brightness(1000))
        self.assertEqual(runtime.display.values, [])
        self.assertEqual(runtime.auto_brightness_applied, runtime.AUTO_BRIGHTNESS_DEFAULT)

    def test_sampling_is_throttled(self):
        runtime.badge = FakeBadge([0, 60000])

        runtime.update_auto_brightness(1000)
        runtime.update_auto_brightness(1100)

        self.assertEqual(runtime.badge.reads, 1)

    def test_feature_disabled_skips_backlight_logic(self):
        runtime.cfg.AUTO_BRIGHTNESS_ENABLED = False
        runtime.badge = FakeBadge([60000])

        self.assertFalse(runtime.update_auto_brightness(1000))
        self.assertEqual(runtime.badge.reads, 0)
        self.assertEqual(runtime.display.values, [])


if __name__ == "__main__":
    unittest.main()
