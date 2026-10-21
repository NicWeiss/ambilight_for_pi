import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ambilight import AmbilightProcessor
from settings import settings


class AmbilightTest(unittest.TestCase):
    def setUp(self):
        self.thickness = settings.LEDS_THICKNESS
        self.bottom = settings.LEDS_BOTTOM

    def tearDown(self):
        settings.LEDS_THICKNESS = self.thickness
        settings.LEDS_BOTTOM = self.bottom

    def test_segment_counts_follow_leds(self):
        left, top, right = AmbilightProcessor().segment_counts()
        self.assertEqual((left, top, right), (settings.LEDS_LEFT, settings.LEDS_TOP, settings.LEDS_RIGHT))

    def test_from_segments_keeps_order_and_led_count(self):
        proc = AmbilightProcessor()
        left, top, right = proc.segment_counts()
        seg = np.zeros((left + top + right, 3), np.float32)
        seg[:left, 0] = 1       # слева
        seg[left:left + top, 0] = 2   # сверху
        seg[left + top:, 0] = 3       # справа
        colors = proc.from_segments(seg)
        self.assertEqual(colors.shape, (settings.LED_COUNT, 3))
        self.assertTrue((colors[:left, 0] == 1).all())
        self.assertTrue((colors[left:left + top, 0] == 2).all())
        self.assertTrue((colors[left + top:, 0] == 3).all())

    def test_thickness_repeats_each_segment(self):
        settings.LEDS_THICKNESS = 2
        proc = AmbilightProcessor()
        left, top, right = proc.segment_counts()
        seg = np.arange((left + top + right) * 3, dtype=np.float32).reshape(-1, 3)
        colors = proc.from_segments(seg)
        self.assertEqual(len(colors), settings.LED_COUNT)
        self.assertTrue((colors[0] == colors[1]).all())
        self.assertTrue((colors[2] == seg[1]).all())

    def test_from_segments_pads_with_black_when_short(self):
        proc = AmbilightProcessor()
        colors = proc.from_segments(np.full((3, 3), 50, np.float32))
        self.assertEqual(len(colors), settings.LED_COUNT)

    def test_smoothing_does_not_depend_on_call_rate(self):
        target = np.full((settings.LED_COUNT, 3), 200, np.float32)
        a, b = AmbilightProcessor(), AmbilightProcessor()
        a.smooth(target, 0.2, 0.1)
        b.smooth(target, 0.1, 0.1)
        b.smooth(target, 0.1, 0.1)
        self.assertTrue(np.allclose(a.smoothed_colors, b.smoothed_colors, atol=1e-3))

    def test_smoothing_converges_to_target(self):
        proc = AmbilightProcessor()
        target = np.full((settings.LED_COUNT, 3), 120, np.float32)
        out = proc.smooth(target, 10.0, 0.1)
        self.assertTrue((out == 120).all())


if __name__ == "__main__":
    unittest.main()
